from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Any

from agentorch import SandboxManager, SandboxPolicy, ToolRegistry, create_agent
from agentorch.config import initialize_environment

from .desktop_tools import build_desktop_tools


DEFAULT_MODEL = os.getenv("DESKTOP_AGENT_MODEL", "gpt-4.1-mini")


def _build_system_prompt(desktop_root: Path, framework_root: Path) -> str:
    return f"""
You are Goblin, a friendly Windows desktop avatar assistant built with the agentorch framework.

You help with three kinds of tasks:
1. Casual chat and companionship.
2. Programming and file-based work inside the user's desktop workspace.
3. Safe desktop cleanup and organization.

Operating rules:
- For desktop cleanup, inspect first. Use list_desktop_items or preview_desktop_organization before suggesting moves.
- Before moving multiple files or folders, ask for a clear confirmation.
- Never delete files. Prefer creating folders and moving items.
- For programming tasks, use the available filesystem and run_command tools when they improve accuracy.
- Keep replies natural and concise, but explain concrete actions you took.
- When a user asks for a desktop action, mention the exact folder or file names involved.
- If the request is risky or ambiguous, pause and ask one concise clarification.

Important paths:
- Desktop root: {desktop_root}
- Framework root: {framework_root}
""".strip()


class DesktopAvatarAgentService:
    def __init__(self, *, desktop_root: Path, framework_root: Path) -> None:
        self.desktop_root = desktop_root.resolve()
        self.framework_root = framework_root.resolve()
        self.workspace_root = self.desktop_root
        self._lock = threading.Lock()
        initialize_environment(self.framework_root / ".env")
        self._agent = self._create_agent()

    def _create_agent(self):
        sandbox = SandboxManager(
            policy=SandboxPolicy(
                allowed_paths=[self.desktop_root, self.framework_root],
                command_allowlist=["python", "py", "git", "powershell", "cmd"],
                timeout=45.0,
                allow_shell=False,
            )
        )

        tools = ToolRegistry.with_bundles(
            workspace_root=self.workspace_root,
            sandbox=sandbox,
            include_filesystem=True,
            include_execution=True,
            include_git=False,
            include_web=False,
        )
        for custom_tool in build_desktop_tools(self.desktop_root):
            tools.register(custom_tool)

        agent = create_agent(
            model=DEFAULT_MODEL,
            system_prompt=_build_system_prompt(self.desktop_root, self.framework_root),
            reasoning="react",
            tools=tools,
            workspace_root=self.workspace_root,
            enable_memory=True,
            name="desktop-goblin-agent",
        )
        return agent

    def chat(self, message: str, *, thread_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        active_thread_id = thread_id or f"desktop-session-{uuid.uuid4()}"
        with self._lock:
            result = self._agent.run_sync(message, thread_id=active_thread_id, metadata=metadata or {})
        tool_results = []
        for item in result.tool_results:
            if hasattr(item, "model_dump"):
                tool_results.append(item.model_dump())
            else:
                tool_results.append(dict(item))
        return {
            "thread_id": active_thread_id,
            "output_text": result.output_text,
            "tool_results": tool_results,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": DEFAULT_MODEL,
            "desktop_root": str(self.desktop_root),
            "framework_root": str(self.framework_root),
        }
