from __future__ import annotations

from pathlib import Path

from agentorch import CoordinationPolicy, OpenAIModel, PydanticParser, create_multi_agent

from projects.ai_short_drama.backend.app.domain.models import AssemblyPlan, DramaProjectRequest, ShortDramaPlan
from projects.ai_short_drama.backend.app.utils.env_loader import get_first_env, load_project_env


def _build_story_prompt(request: DramaProjectRequest) -> str:
    return f"""
你们是 AI 短剧团队，请协作完成首版短剧规划。

输入信息：
- 项目名称：{request.project_name}
- premise：{request.premise}
- 风格：{request.style}
- 目标：{request.episode_goal}
- 角色数量：{request.role_count}
- 镜头数量：{request.shot_count}

产出要求：
1. 输出必须是一个合法 JSON。
2. 顶层字段必须包含：project_title、logline、visual_style、episode_summary、roles、shots。
3. roles 内每个对象必须含：name、appearance、personality、relationship、avatar_prompt、voice_style。
4. shots 内每个对象必须含：shot_no、title、summary、duration_seconds、ratio、first_frame_prompt、video_prompt、subtitle_text、focus_roles。
5. 请让 reviewer 主动检查角色一致性、镜头连续性、提示词是否适合图像和视频生成。
6. duration_seconds 必须严格落在 4 到 15 秒之间，优先使用 4 到 6 秒。
""".strip()


def _build_assembly_prompt(plan: ShortDramaPlan) -> str:
    shot_lines = []
    for shot in plan.shots:
        shot_lines.append(
            f"镜头{shot.shot_no}《{shot.title}》：{shot.summary}；时长 {shot.duration_seconds}s；字幕：{shot.subtitle_text or '无'}"
        )
    shot_block = "\n".join(shot_lines)
    return f"""
你们是 AI 短剧后期团队，请基于现有镜头方案设计成片装配方案。

剧集标题：{plan.project_title}
一句话梗概：{plan.logline}
整体风格：{plan.visual_style}
镜头列表：
{shot_block}

输出要求：
1. 只输出合法 JSON。
2. 顶层字段必须有：episode_title、editing_style、transitions、final_runtime_seconds、export_notes。
3. transitions 里的每个对象必须含：transition_no、from_shot_no、to_shot_no、transition_type、duration_seconds、visual_prompt、summary。
4. 转场要服务叙事，不要机械重复。
5. export_notes 里要包含对字幕、封面、失败重跑或后期拼接的提醒。
""".strip()


class AgentTorchDramaTeamService:
    """把短剧规划和装配显式封装成 AgentTorch 多智能体团队。"""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        load_project_env(self.workspace_root)

        model_name = get_first_env("OPENAI_CHAT_MODEL", "OPENAI_MODEL", "AGENTORCH_MODEL")
        api_key = get_first_env("OPENAI_API_KEY")
        base_url = get_first_env("OPENAI_BASE_URL")
        if not model_name or not api_key or not base_url:
            raise ValueError("LLM 配置缺失，请检查 OPENAI_CHAT_MODEL / OPENAI_API_KEY / OPENAI_BASE_URL")

        self.shared_model = OpenAIModel(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
            max_retries=1,
        )
        self.story_team = create_multi_agent(
            name="short-drama-story-team",
            system_prompt="你们共同负责 AI 短剧策划，输出要严谨、结构化、可落地。",
            coordination_policy=CoordinationPolicy.distributed(),
            roles=[
                {
                    "name": "writer",
                    "description": "负责编剧与人物设定",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": True,
                },
                {
                    "name": "director",
                    "description": "负责镜头调度和视觉设计",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": True,
                },
                {
                    "name": "reviewer",
                    "description": "负责审校角色一致性与镜头闭环",
                    "model": self.shared_model,
                    "capabilities": ["review"],
                    "supports_parallel_tasks": True,
                },
            ],
        )
        self.assembly_team = create_multi_agent(
            name="short-drama-assembly-team",
            system_prompt="你们共同负责短剧后期装配方案，重点关注转场、节奏和最终导出。",
            coordination_policy=CoordinationPolicy.distributed(),
            roles=[
                {
                    "name": "editor",
                    "description": "负责剪辑结构和节奏安排",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": True,
                },
                {
                    "name": "transition_designer",
                    "description": "负责转场设计和视觉过渡",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": True,
                },
                {
                    "name": "qc_reviewer",
                    "description": "负责成片风险检查和导出说明",
                    "model": self.shared_model,
                    "capabilities": ["review"],
                    "supports_parallel_tasks": True,
                },
            ],
        )

    def generate_story_plan(self, request: DramaProjectRequest, *, thread_id: str) -> ShortDramaPlan:
        result = self.story_team.run_parsed_sync(
            _build_story_prompt(request),
            thread_id=thread_id,
            parser=PydanticParser(ShortDramaPlan),
        )
        return result.parsed

    def generate_assembly_plan(self, plan: ShortDramaPlan, *, thread_id: str) -> AssemblyPlan:
        result = self.assembly_team.run_parsed_sync(
            _build_assembly_prompt(plan),
            thread_id=thread_id,
            parser=PydanticParser(AssemblyPlan),
        )
        return result.parsed

    def close(self) -> None:
        for runtime_holder in (self.story_team, self.assembly_team):
            try:
                runtime_holder.close()
            except RuntimeError:
                pass
