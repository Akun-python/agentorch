from __future__ import annotations

from pathlib import Path

from agentorch import OpenAIModel, PydanticParser, create_agent

from projects.ai_short_drama.backend.app.domain.models import DramaProjectRequest, ShortDramaPlan
from projects.ai_short_drama.backend.app.utils.env_loader import get_first_env, load_project_env


def _build_prompt(request: DramaProjectRequest) -> str:
    return f"""
请根据下面要求，生成一个适合 AI 短剧首版闭环的结果。

项目名称：{request.project_name}
故事 premise：{request.premise}
整体风格：{request.style}
本次目标：{request.episode_goal}
角色数量：{request.role_count}
镜头数量：{request.shot_count}

硬性要求：
1. roles 数量必须严格等于角色数量。
2. shots 数量必须严格等于镜头数量。
3. roles 里的每个对象必须包含字段：name、appearance、personality、relationship、avatar_prompt、voice_style。
4. shots 里的每个对象必须包含字段：shot_no、title、summary、duration_seconds、ratio、first_frame_prompt、end_frame_prompt、video_prompt、continuity_notes、camera_axis、lighting_state、prop_state、character_state、subtitle_text、focus_roles。
5. project_title、logline、visual_style、episode_summary 这 4 个顶层字段必须存在。
6. end_frame_prompt 必须描述镜头结束时的定格画面，用于目标尾帧参考图。
7. continuity_notes 必须拆成数组，逐条写角色、道具、视线、光线和动作惯性。
8. camera_axis 必须含 axis_description、screen_direction、camera_position。
9. lighting_state 必须含 key_light_direction、color_temperature、brightness_level。
10. prop_state 必须含 prop_name、placement、orientation、hand_usage、continuity_priority；没有明确道具时返回空数组。
11. character_state 必须对每个 focus_roles 角色写 name、blocking、pose、expression、eyeline、wardrobe_state。
12. avatar_prompt、first_frame_prompt、end_frame_prompt、video_prompt 必须是可以直接给图像/视频模型使用的中文提示词。
13. 角色外形、镜头视觉和动作描述要一致，不要互相打架。
14. shot_no 从 1 开始连续递增。
15. duration_seconds 默认 4 到 6 秒之间。
16. 不要输出 Markdown，不要解释，只返回符合 schema 的 JSON。
""".strip()


class AgentTorchStoryPlanner:
    """用 AgentTorch 生成角色设定和镜头方案。"""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        load_project_env(self.workspace_root)

        model_name = get_first_env("OPENAI_CHAT_MODEL", "OPENAI_MODEL", "AGENTORCH_MODEL")
        api_key = get_first_env("OPENAI_API_KEY")
        base_url = get_first_env("OPENAI_BASE_URL")
        if not model_name or not api_key or not base_url:
            raise ValueError("LLM 配置缺失，请检查 OPENAI_CHAT_MODEL / OPENAI_API_KEY / OPENAI_BASE_URL")

        self.model = OpenAIModel(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
            max_retries=1,
        )
        self.agent = create_agent(
            model=self.model,
            workspace_root=self.workspace_root,
            system_prompt=(
                "你是中文短剧总编剧兼分镜策划。"
                "你的输出必须结构清晰、角色一致、镜头可直接用于出图和首帧生视频。"
            ),
            reasoning="react",
            name="short-drama-planner",
        )

    def generate_plan(self, request: DramaProjectRequest, *, thread_id: str) -> ShortDramaPlan:
        parser = PydanticParser(ShortDramaPlan)
        result = self.agent.run_parsed_sync(
            _build_prompt(request),
            thread_id=thread_id,
            parser=parser,
        )
        return result.parsed

    def close(self) -> None:
        try:
            self.agent.runtime.close()
        except RuntimeError:
            # Windows 上连接回收偶发 event loop 关闭噪声，不影响本次产物
            pass
