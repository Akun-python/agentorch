from __future__ import annotations

from pathlib import Path

from agentorch import CoordinationPolicy, OpenAIModel, create_multi_agent

from projects.ai_short_drama.backend.app.domain.models import AssemblyPlan, DramaProjectRequest, ShortDramaPlan
from projects.ai_short_drama.backend.app.services.drama_output_parse_service import DramaPydanticRepairParser
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
1.1 最终回答只能输出一个 JSON 对象，不要带 [writer]/[director]/[reviewer] 前缀，不要输出 Markdown 代码块。
2. 顶层字段必须包含：project_title、logline、visual_style、episode_summary、roles、shots。
3. roles 内每个对象必须含：name、appearance、personality、relationship、avatar_prompt、voice_style。
4. shots 内每个对象必须含：shot_no、title、summary、duration_seconds、ratio、first_frame_prompt、video_prompt、subtitle_text、focus_roles。
5. shots 内还必须尽量补充：end_frame_prompt、continuity_notes、camera_axis、lighting_state、prop_state、character_state。
6. end_frame_prompt 必须写清镜头结束时定格的画面，能直接用于生成目标尾帧参考图。
7. continuity_notes 必须逐条写清和上一镜头衔接的角色、道具、光线、视线和动作惯性。
8. camera_axis 必须含 axis_description、screen_direction、camera_position。
9. lighting_state 必须含 key_light_direction、color_temperature、brightness_level。
10. prop_state 必须含关键道具的 prop_name、placement、orientation、hand_usage、continuity_priority；没有明确道具时返回空数组。
11. character_state 必须对 focus_roles 中每个角色写 name、blocking、pose、expression、eyeline、wardrobe_state。
12. 请让 reviewer 主动检查角色一致性、镜头连续性、提示词是否适合图像和视频生成。
13. duration_seconds 必须严格落在 4 到 15 秒之间，优先使用 4 到 6 秒；若需要更长动作，仍保持单镜头可被后续分段生成。
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
1.1 最终回答只能输出一个 JSON 对象，不要带 [editor]/[transition_designer]/[qc_reviewer] 前缀，不要输出 Markdown 代码块。
2. 顶层字段必须有：episode_title、editing_style、transitions、final_runtime_seconds、export_notes。
3. transitions 里的每个对象必须含：transition_no、from_shot_no、to_shot_no、transition_type、duration_seconds、overlap_seconds、audio_bridge、visual_prompt、summary。
4. overlap_seconds 控制相邻镜头交叠区，通常 0.25 到 0.6 秒，动作连续时可以稍长。
5. audio_bridge 要写明环境声、音乐或动作音效如何跨过剪辑点，避免声音硬断。
6. 转场要服务叙事，不要机械重复。
7. export_notes 里要包含对字幕、封面、失败重跑或后期拼接的提醒。
""".strip()


class AgentTorchDramaTeamService:
    """把短剧规划和装配显式封装成 AgentTorch 多智能体团队。"""

    def __init__(self, workspace_root: Path, request: DramaProjectRequest | None = None):
        self.workspace_root = Path(workspace_root)
        self.request = request
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
            timeout=request.llm_timeout_seconds if request else 240.0,
            max_retries=request.llm_max_retries if request else 2,
            retry_base_delay=request.llm_retry_base_delay_seconds if request else 3.0,
            retry_max_delay=request.llm_retry_max_delay_seconds if request else 60.0,
            min_request_interval=request.llm_min_request_interval_seconds if request else 0.0,
            max_tokens=request.llm_max_tokens if request else 4096,
        )
        coordination_policy = _build_coordination_policy(request)
        supports_parallel_tasks = bool(request.llm_parallel_agents) if request else True
        self.story_team = create_multi_agent(
            name="short-drama-story-team",
            system_prompt="你们共同负责 AI 短剧策划，输出要严谨、结构化、可落地。",
            coordination_policy=coordination_policy,
            roles=[
                {
                    "name": "writer",
                    "description": "负责编剧与人物设定",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
                {
                    "name": "director",
                    "description": "负责镜头调度和视觉设计",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
                {
                    "name": "reviewer",
                    "description": "负责审校角色一致性与镜头闭环",
                    "model": self.shared_model,
                    "capabilities": ["review"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
            ],
        )
        self.assembly_team = create_multi_agent(
            name="short-drama-assembly-team",
            system_prompt="你们共同负责短剧后期装配方案，重点关注转场、节奏和最终导出。",
            coordination_policy=coordination_policy,
            roles=[
                {
                    "name": "editor",
                    "description": "负责剪辑结构和节奏安排",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
                {
                    "name": "transition_designer",
                    "description": "负责转场设计和视觉过渡",
                    "model": self.shared_model,
                    "capabilities": ["plan"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
                {
                    "name": "qc_reviewer",
                    "description": "负责成片风险检查和导出说明",
                    "model": self.shared_model,
                    "capabilities": ["review"],
                    "supports_parallel_tasks": supports_parallel_tasks,
                },
            ],
        )

    def generate_story_plan(self, request: DramaProjectRequest, *, thread_id: str) -> ShortDramaPlan:
        result = self.story_team.run_parsed_sync(
            _build_story_prompt(request),
            thread_id=thread_id,
            parser=DramaPydanticRepairParser(ShortDramaPlan),
        )
        return result.parsed

    def generate_assembly_plan(self, plan: ShortDramaPlan, *, thread_id: str) -> AssemblyPlan:
        result = self.assembly_team.run_parsed_sync(
            _build_assembly_prompt(plan),
            thread_id=thread_id,
            parser=DramaPydanticRepairParser(AssemblyPlan),
        )
        return result.parsed

    def close(self) -> None:
        for runtime_holder in (self.story_team, self.assembly_team):
            try:
                runtime_holder.close()
            except RuntimeError:
                pass


def _build_coordination_policy(request: DramaProjectRequest | None) -> CoordinationPolicy:
    if request is None:
        return CoordinationPolicy.distributed()
    if not request.llm_parallel_agents:
        return CoordinationPolicy(route_mode="guided", handoff_mode="summary_only", alert_mode="shared")
    if request.agent_coordination_mode == "distributed":
        return CoordinationPolicy.distributed()
    if request.agent_coordination_mode == "hybrid":
        return CoordinationPolicy.hybrid()
    return CoordinationPolicy(route_mode="guided", handoff_mode="summary_only", alert_mode="shared")
