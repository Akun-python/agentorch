from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class RoleCard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="角色名")
    appearance: str = Field(..., description="外形特征")
    personality: str = Field(
        ...,
        description="性格设定",
        validation_alias=AliasChoices("personality", "description", "trait"),
    )
    relationship: str = Field(
        ...,
        description="与主线关系",
        validation_alias=AliasChoices("relationship", "dramatic_function", "role_function"),
    )
    avatar_prompt: str = Field(..., description="角色立绘提示词")
    voice_style: str = Field(
        ...,
        description="建议音色风格",
        validation_alias=AliasChoices("voice_style", "voice", "voice_tone"),
    )

    @model_validator(mode="before")
    @classmethod
    def fill_compatible_fields(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("personality"):
            payload["personality"] = payload.get("description") or f"符合角色设定：{payload.get('name') or payload.get('role_name', '未命名角色')}"
        if not payload.get("relationship"):
            payload["relationship"] = payload.get("dramatic_function") or "与主线强相关的关键角色"
        if not payload.get("voice_style"):
            payload["voice_style"] = "情绪克制、适合中文短剧对白"
        if not payload.get("name") and payload.get("role_name"):
            payload["name"] = payload["role_name"]
        return payload


class ShotPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    shot_no: int = Field(..., ge=1)
    title: str = Field(
        ...,
        description="镜头标题",
        validation_alias=AliasChoices("title", "shot_title", "name"),
    )
    summary: str = Field(
        ...,
        description="镜头摘要",
        validation_alias=AliasChoices("summary", "description"),
    )
    duration_seconds: int = Field(default=4, ge=4, le=15)
    ratio: str = Field(default="16:9")
    first_frame_prompt: str = Field(..., description="首帧图提示词")
    video_prompt: str = Field(..., description="图生视频提示词")
    subtitle_text: str = Field(default="", description="字幕文案")
    focus_roles: list[str] = Field(default_factory=list, description="重点角色名")

    @model_validator(mode="before")
    @classmethod
    def fill_compatible_fields(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("title"):
            shot_no = payload.get("shot_no", "x")
            payload["title"] = f"镜头{shot_no}"
        if not payload.get("summary"):
            payload["summary"] = payload.get("description") or payload.get("video_prompt") or ""
        if not payload.get("focus_roles"):
            payload["focus_roles"] = []
        return payload


class ShortDramaPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_title: str = Field(
        ...,
        description="项目标题",
        validation_alias=AliasChoices("project_title", "project_name", "title"),
    )
    logline: str = Field(
        ...,
        description="一句话梗概",
        validation_alias=AliasChoices("logline", "premise", "hook"),
    )
    visual_style: str = Field(
        ...,
        description="整体视觉风格",
        validation_alias=AliasChoices("visual_style", "genre", "style"),
    )
    episode_summary: str = Field(
        ...,
        description="这一集的摘要",
        validation_alias=AliasChoices("episode_summary", "episode_outline", "summary"),
    )
    roles: list[RoleCard] = Field(default_factory=list)
    shots: list[ShotPlan] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def fill_compatible_fields(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("episode_summary"):
            shot_descriptions = []
            for shot in payload.get("shots") or []:
                if isinstance(shot, dict) and shot.get("description"):
                    shot_descriptions.append(shot["description"])
            payload["episode_summary"] = "；".join(shot_descriptions[:3]) or payload.get("premise") or ""
        return payload


class DramaProjectRequest(BaseModel):
    project_name: str = Field(..., description="项目名称")
    premise: str = Field(..., description="故事 premise")
    style: str = Field(default="都市悬疑短剧", description="整体风格")
    episode_goal: str = Field(default="先生成一集的开场段落", description="本次目标")
    role_count: int = Field(default=2, ge=1, le=8)
    shot_count: int = Field(default=2, ge=1, le=8)
    image_aspect_ratio: str = Field(default="16:9")
    generate_role_images: bool = Field(default=True)
    generate_storyboard_images: bool = Field(default=True)
    generate_shot_videos: bool = Field(default=True)
    render_role_image_limit: int = Field(default=2, ge=0, le=8)
    render_shot_limit: int = Field(default=1, ge=0, le=8)
    project_id: str | None = Field(default=None)


class GeneratedAsset(BaseModel):
    asset_type: str
    relative_path: str
    source_name: str
    metadata: dict = Field(default_factory=dict)


class DramaPipelineResult(BaseModel):
    project_id: str
    project_dir: str
    request_path: str
    plan_path: str
    manifest_path: str
    generated_assets: list[GeneratedAsset] = Field(default_factory=list)
