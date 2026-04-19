from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .agents import build_harness_agents
from .bootstrap import ensure_repo_root_on_path
from .config import HarnessConfig
from .env import load_harness_environment
from .loop import HarnessLoop
from .memory_store import build_memory_manager
from .progress import ConsoleProgressReporter, NullProgressReporter, ProgressReporter
from .review_tools import ReviewCollector
from .session_manager import SessionManager
from .state_store import StateStore
from .tools import build_tool_registry
from .workspace_manager import WorkspaceManager

ensure_repo_root_on_path()

from agentorch import HumanFeedbackManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex supervisory harness built on AgentTorch.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create runtime directories for codexharness.")
    init_parser.add_argument("--project-root", required=True, help="Target repository or project root.")
    init_parser.add_argument("--env-file", help="Optional .env file to load before the command runs.")

    run_parser = subparsers.add_parser("run", help="Run a Phase 1 supervisory loop.")
    _add_common_runtime_args(run_parser)
    run_parser.add_argument("--prompt", help="Top-level user request.")
    run_parser.add_argument("--prompt-file", help="Read the top-level request from a UTF-8 text file.")
    run_parser.add_argument("--no-progress", action="store_true", help="Disable live progress messages on stderr.")

    resume_parser = subparsers.add_parser("resume", help="Resume from the latest or a specific checkpointed run.")
    _add_common_runtime_args(resume_parser)
    resume_parser.add_argument("--run-id", help="Explicit run id to resume.")
    resume_parser.add_argument("--latest", action="store_true", help="Resume the latest available run.")
    resume_parser.add_argument("--no-progress", action="store_true", help="Disable live progress messages on stderr.")
    return parser


async def run_command(args: argparse.Namespace) -> int:
    config = _build_config_from_args(args)
    try:
        config.validate_runtime_requirements()
    except ValueError as exc:
        raise SystemExit(str(exc))
    config.ensure_runtime_layout()
    user_request = _resolve_prompt(args)
    progress = _build_progress_reporter(disabled=getattr(args, "no_progress", False))
    _, loop = _build_runtime(config, progress=progress)
    state = await loop.run(user_request=user_request)
    _print_state(state)
    return 0 if state.overall_status == "completed" else 1


async def resume_command(args: argparse.Namespace) -> int:
    config = _build_config_from_args(args)
    try:
        config.validate_runtime_requirements()
    except ValueError as exc:
        raise SystemExit(str(exc))
    config.ensure_runtime_layout()
    progress = _build_progress_reporter(disabled=getattr(args, "no_progress", False))
    state_store, loop = _build_runtime(config, progress=progress)
    run_id = args.run_id
    if run_id is None and args.latest:
        run_id = state_store.latest_run_id()
    state = await loop.resume(run_id=run_id)
    _print_state(state)
    return 0 if state.overall_status == "completed" else 1


def init_command(args: argparse.Namespace) -> int:
    config = HarnessConfig(project_root=Path(args.project_root))
    config.ensure_runtime_layout()
    print(f"Initialized codexharness runtime under: {config.runtime_root}")
    print(f"Worktrees root: {config.worktree_root}")
    return 0


def _add_common_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", required=True, help="Target repository or project root.")
    parser.add_argument("--env-file", help="Optional .env file to load before the command runs.")
    parser.add_argument("--model", default=None, help="Agent model name. Defaults to .env/ENV if omitted.")
    parser.add_argument("--codex-model", default=None, help="Codex child-task model name. Defaults to .env/ENV if omitted.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum supervisory rounds.")
    parser.add_argument("--max-parallel-tasks", type=int, default=2, help="Maximum concurrent child Codex tasks.")
    parser.add_argument("--planner-max-tasks", type=int, default=4, help="Maximum tasks created by the planner stage.")
    parser.add_argument("--max-task-retries", type=int, default=1, help="Maximum follow-up retries per task.")
    parser.add_argument(
        "--workspace-mode",
        choices=["shared", "git-worktree", "copy"],
        default="shared",
        help="Workspace allocation strategy for write tasks.",
    )
    parser.add_argument("--codex-binary", default=None, help="Path or command name for the Codex CLI.")
    parser.add_argument("--codex-sandbox", default="workspace-write", help="Sandbox mode passed to Codex child tasks.")
    parser.add_argument("--codex-approval", default="never", help="Approval policy passed to Codex child tasks.")
    parser.add_argument("--codex-skip-git-repo-check", action="store_true", help="Pass --skip-git-repo-check to Codex child tasks.")
    parser.add_argument(
        "--disable-human-feedback",
        action="store_true",
        help="Disable AgentTorch human feedback plumbing.",
    )


def _build_config_from_args(args: argparse.Namespace) -> HarnessConfig:
    payload = {
        "project_root": Path(args.project_root),
        "max_rounds": args.max_rounds,
        "max_parallel_tasks": args.max_parallel_tasks,
        "planner_max_tasks": args.planner_max_tasks,
        "max_task_retries": args.max_task_retries,
        "workspace_mode": args.workspace_mode,
        "codex_sandbox": args.codex_sandbox,
        "codex_approval": args.codex_approval,
        "codex_skip_git_repo_check": args.codex_skip_git_repo_check,
        "enable_human_feedback": not args.disable_human_feedback,
    }
    if args.model is not None:
        payload["model_name"] = args.model
    if args.codex_model is not None:
        payload["codex_model_name"] = args.codex_model
    if args.codex_binary is not None:
        payload["codex_binary"] = args.codex_binary
    return HarnessConfig(**payload)


def _build_runtime(config: HarnessConfig, *, progress: ProgressReporter | None = None) -> tuple[StateStore, HarnessLoop]:
    state_store = StateStore(config)
    workspace_manager = WorkspaceManager(config)
    session_manager = SessionManager(config, state_store)
    review_collector = ReviewCollector(config, state_store)
    memory = build_memory_manager(config)
    feedback = HumanFeedbackManager.enabled() if config.enable_human_feedback else None
    tool_registry = build_tool_registry(
        workspace_manager=workspace_manager,
        session_manager=session_manager,
        review_collector=review_collector,
    )
    agents = build_harness_agents(
        config=config,
        tools=tool_registry,
        memory=memory,
        feedback=feedback,
    )
    loop = HarnessLoop(
        config=config,
        agents=agents,
        state_store=state_store,
        session_manager=session_manager,
        workspace_manager=workspace_manager,
        review_collector=review_collector,
        progress=progress,
    )
    return state_store, loop


def _build_progress_reporter(*, disabled: bool) -> ProgressReporter:
    if disabled:
        return NullProgressReporter()
    return ConsoleProgressReporter(enabled=True)


def _print_state(state) -> None:
    print(
        json.dumps(
            {
                "run_id": state.run_id,
                "thread_id": state.thread_id,
                "overall_status": state.overall_status,
                "summary": state.summary,
                "tasks": [item.model_dump(mode="json") for item in state.tasks],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _resolve_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return data
    raise SystemExit("A prompt is required. Provide --prompt, --prompt-file, or stdin.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    load_harness_environment(project_root=Path(args.project_root), env_file=getattr(args, "env_file", None))
    if args.command == "init":
        raise SystemExit(init_command(args))
    if args.command == "run":
        raise SystemExit(asyncio.run(run_command(args)))
    if args.command == "resume":
        raise SystemExit(asyncio.run(resume_command(args)))


if __name__ == "__main__":
    main()
