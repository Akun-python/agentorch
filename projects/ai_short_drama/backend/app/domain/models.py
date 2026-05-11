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


class CameraAxisState(BaseModel):
    axis_description: str = Field(default="主体主运动方向保持稳定", description="轴线说明")
    screen_direction: str = Field(default="主体由左向右推进", description="主体在画面中的方向")
    camera_position: str = Field(default="镜头保持在同一轴线侧", description="机位所在轴线侧")


class LightingState(BaseModel):
    key_light_direction: str = Field(default="主光从画面左前方打入", description="主光方向")
    color_temperature: str = Field(default="冷中性", description="色温状态")
    brightness_level: str = Field(default="中低照度，保留戏剧反差", description="明暗级别")


class PropContinuityState(BaseModel):
    prop_name: str
    placement: str = Field(default="保持在镜头主动作区域", description="道具位置")
    orientation: str = Field(default="朝向与上一镜头一致", description="道具朝向")
    hand_usage: str = Field(default="保持手位一致", description="持握方式")
    continuity_priority: str = Field(default="medium", description="连续性优先级")


class CharacterContinuityState(BaseModel):
    name: str
    blocking: str = Field(default="保持与上一镜头衔接的站位", description="人物站位")
    pose: str = Field(default="动作起势延续上一镜头尾帧", description="姿态状态")
    expression: str = Field(default="情绪延续当前剧情推进", description="表情状态")
    eyeline: str = Field(default="视线方向保持对位逻辑", description="视线方向")
    wardrobe_state: str = Field(default="服装、发型、妆面保持一致", description="服装状态")


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
    end_frame_prompt: str = Field(default="", description="尾帧目标提示词")
    video_prompt: str = Field(..., description="图生视频提示词")
    continuity_notes: list[str] = Field(default_factory=list, description="连续性要求")
    camera_axis: CameraAxisState = Field(default_factory=CameraAxisState)
    lighting_state: LightingState = Field(default_factory=LightingState)
    prop_state: list[PropContinuityState] = Field(default_factory=list, description="关键道具状态")
    character_state: list[CharacterContinuityState] = Field(default_factory=list, description="人物连续性状态")
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
        if payload.get("duration_seconds") is not None:
            try:
                duration_value = int(payload["duration_seconds"])
            except (TypeError, ValueError):
                duration_value = 4
            payload["duration_seconds"] = max(4, min(15, duration_value))
        if not payload.get("focus_roles"):
            payload["focus_roles"] = []
        if not payload.get("end_frame_prompt"):
            payload["end_frame_prompt"] = f"{payload['title']}结束时的关键画面，动作收束并给下镜头留钩子"
        continuity_notes = payload.get("continuity_notes")
        if isinstance(continuity_notes, str):
            continuity_notes = [continuity_notes]
        if not continuity_notes:
            continuity_notes = [
                "人物站位、服装与发型保持稳定延续",
                "关键道具的位置、朝向和持握手保持一致",
                "主光方向、色温和场景总体明暗不可突变",
            ]
        payload["continuity_notes"] = continuity_notes
        if not payload.get("camera_axis"):
            payload["camera_axis"] = {
                "axis_description": "保持同一叙事轴线，避免无原因跳轴",
                "screen_direction": "主体动作方向与上一镜头连续",
                "camera_position": "机位保持在同一轴线侧，必要时只做轻微推进",
            }
        if not payload.get("lighting_state"):
            payload["lighting_state"] = {
                "key_light_direction": "主光方向延续上一镜头",
                "color_temperature": "色温保持统一，不要冷暖乱跳",
                "brightness_level": "亮度围绕当前场景稳定波动",
            }
        if not payload.get("character_state"):
            payload["character_state"] = [
                {
                    "name": role_name,
                    "blocking": "延续上一镜头的空间关系",
                    "pose": "动作起势和重心与上一镜头尾帧对齐",
                    "expression": "表情延续当前剧情冲突",
                    "eyeline": "视线方向与对手戏或目标物一致",
                    "wardrobe_state": "服装和发型保持连续",
                }
                for role_name in payload.get("focus_roles") or []
            ]
        if payload.get("prop_state") is None:
            payload["prop_state"] = []
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


class TransitionPlan(BaseModel):
    transition_no: int = Field(..., ge=1)
    from_shot_no: int = Field(..., ge=1)
    to_shot_no: int = Field(..., ge=1)
    transition_type: str = Field(default="fade", description="转场类型")
    duration_seconds: float = Field(default=0.6, ge=0.1, le=3.0)
    overlap_seconds: float = Field(default=0.35, ge=0.0, le=1.5, description="与下一镜头交叠时长")
    audio_bridge: str = Field(default="延续环境底噪并轻微跨淡到下一镜头", description="音频衔接说明")
    visual_prompt: str = Field(default="", description="转场画面提示词")
    summary: str = Field(default="", description="转场说明")


class AssemblyPlan(BaseModel):
    episode_title: str = Field(..., description="成片标题")
    editing_style: str = Field(..., description="剪辑风格")
    transitions: list[TransitionPlan] = Field(default_factory=list)
    final_runtime_seconds: float = Field(default=0.0, ge=0.0)
    export_notes: list[str] = Field(default_factory=list)


class ProductionStageRecord(BaseModel):
    stage_name: str
    status: str
    detail: str = ""
    metadata: dict = Field(default_factory=dict)


class StoryBible(BaseModel):
    title: str
    core_theme: str = Field(default="", description="核心主题")
    emotional_hook: str = Field(default="", description="情绪抓手")
    world_rules: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)
    forbidden_cliches: list[str] = Field(default_factory=list)
    target_audience: str = Field(default="", description="目标观众")
    must_have_moments: list[str] = Field(default_factory=list)


class CharacterDirection(BaseModel):
    name: str
    dramatic_need: str = Field(default="", description="角色欲望")
    fear_or_wound: str = Field(default="", description="角色伤口")
    arc_start: str = Field(default="", description="弧线起点")
    arc_end_hint: str = Field(default="", description="弧线终点提示")
    body_language: str = Field(default="", description="肢体习惯")
    speech_style: str = Field(default="", description="说话风格")
    visual_anchor: str = Field(default="", description="视觉锚点")
    performance_notes: list[str] = Field(default_factory=list)


class CharacterBible(BaseModel):
    characters: list[CharacterDirection] = Field(default_factory=list)


class SceneBeat(BaseModel):
    scene_no: int = Field(..., ge=1)
    location: str = Field(default="")
    dramatic_goal: str = Field(default="", description="本场戏目标")
    conflict: str = Field(default="", description="冲突来源")
    emotional_turn: str = Field(default="", description="情绪转折")
    reveal: str = Field(default="", description="信息揭示")
    exit_hook: str = Field(default="", description="离场钩子")


class SceneBeatSheet(BaseModel):
    scenes: list[SceneBeat] = Field(default_factory=list)


class ShotDirectionCard(BaseModel):
    shot_no: int = Field(..., ge=1)
    title: str
    story_purpose: str = Field(default="", description="叙事目的")
    framing: str = Field(default="", description="构图")
    camera_angle: str = Field(default="", description="机位角度")
    camera_movement: str = Field(default="", description="镜头运动")
    lens_feel: str = Field(default="", description="镜头质感")
    lighting_notes: str = Field(default="", description="灯光说明")
    acting_notes: list[str] = Field(default_factory=list)
    prop_notes: list[str] = Field(default_factory=list)
    sound_notes: list[str] = Field(default_factory=list)
    continuity_risks: list[str] = Field(default_factory=list)


class DirectorNotebook(BaseModel):
    episode_title: str
    directing_strategy: str = Field(default="", description="整体导演策略")
    pacing_plan: list[str] = Field(default_factory=list)
    visual_motifs: list[str] = Field(default_factory=list)
    actor_guidance: list[str] = Field(default_factory=list)
    shot_cards: list[ShotDirectionCard] = Field(default_factory=list)


class QualityCheckItem(BaseModel):
    item_no: int = Field(..., ge=1)
    category: str
    description: str
    severity: str = Field(default="medium")
    suggestion: str = Field(default="")


class QualityCheckReport(BaseModel):
    summary: str = Field(default="")
    checks: list[QualityCheckItem] = Field(default_factory=list)


class ShotExecutionBeat(BaseModel):
    beat_no: int = Field(..., ge=1)
    shot_no: int = Field(..., ge=1)
    start_seconds: float = Field(..., ge=0.0)
    end_seconds: float = Field(..., ge=0.0)
    focus: str = Field(default="", description="本拍关注点")
    action: str = Field(default="", description="角色或镜头动作")
    emotion: str = Field(default="", description="情绪状态")
    camera_note: str = Field(default="", description="镜头执行说明")


class ShotExecutionSheet(BaseModel):
    beats: list[ShotExecutionBeat] = Field(default_factory=list)


class ShotSegmentPlanItem(BaseModel):
    shot_no: int = Field(..., ge=1)
    segment_no: int = Field(..., ge=1)
    segment_count: int = Field(..., ge=1)
    start_seconds: float = Field(..., ge=0.0)
    end_seconds: float = Field(..., ge=0.0)
    duration_seconds: int = Field(..., ge=4, le=15)
    prompt_focus: str = Field(default="", description="本段生成重点")
    continuity_goal: str = Field(default="", description="本段连续性目标")
    target_end_frame: str = Field(default="", description="本段结束画面目标")


class ShotSegmentPlanSheet(BaseModel):
    segments: list[ShotSegmentPlanItem] = Field(default_factory=list)


class SubtitleSegment(BaseModel):
    segment_no: int = Field(..., ge=1)
    shot_no: int = Field(..., ge=1)
    start_seconds: float = Field(..., ge=0.0)
    end_seconds: float = Field(..., ge=0.0)
    text: str
    emphasis: str = Field(default="", description="强调方式")
    placement: str = Field(default="bottom_center", description="字幕位置")
    animation_style: str = Field(default="fade_in", description="字幕动画")


class SubtitleTimeline(BaseModel):
    segments: list[SubtitleSegment] = Field(default_factory=list)


class AudioCue(BaseModel):
    cue_no: int = Field(..., ge=1)
    shot_no: int | None = Field(default=None, ge=1)
    cue_type: str = Field(default="ambience")
    start_seconds: float = Field(..., ge=0.0)
    end_seconds: float = Field(..., ge=0.0)
    description: str
    intensity: str = Field(default="medium")
    sync_target: str = Field(default="", description="对齐对象")


class AudioCueSheet(BaseModel):
    cues: list[AudioCue] = Field(default_factory=list)


class ContinuityChecklistItem(BaseModel):
    item_no: int = Field(..., ge=1)
    shot_no: int = Field(..., ge=1)
    category: str
    description: str
    check_method: str = Field(default="")
    risk_level: str = Field(default="medium")


class ContinuityChecklist(BaseModel):
    items: list[ContinuityChecklistItem] = Field(default_factory=list)


class ContinuityCheckResult(BaseModel):
    shot_no: int = Field(..., ge=1)
    segment_no: int = Field(..., ge=1)
    attempt_no: int = Field(default=0, ge=0)
    passed: bool = Field(default=True)
    score: float = Field(default=100.0, ge=0.0, le=100.0)
    issues: list[str] = Field(default_factory=list)
    retry_prompt_suffix: str = Field(default="", description="重试时附加提示词")
    metrics: dict = Field(default_factory=dict)


class ContinuityCheckReport(BaseModel):
    checks: list[ContinuityCheckResult] = Field(default_factory=list)


class PropInventoryItem(BaseModel):
    prop_name: str
    used_in_shots: list[int] = Field(default_factory=list)
    continuity_note: str = Field(default="")
    visual_priority: str = Field(default="medium")


class PropInventory(BaseModel):
    items: list[PropInventoryItem] = Field(default_factory=list)


class DeliveryChecklistItem(BaseModel):
    item_no: int = Field(..., ge=1)
    stage: str
    description: str
    owner: str = Field(default="production")
    done_definition: str = Field(default="")


class DeliveryChecklist(BaseModel):
    items: list[DeliveryChecklistItem] = Field(default_factory=list)


class ProjectFileIndexItem(BaseModel):
    stage_name: str
    file_path: str
    description: str


class ProjectFileIndex(BaseModel):
    project_id: str
    items: list[ProjectFileIndexItem] = Field(default_factory=list)


class ExportPackageFile(BaseModel):
    asset_type: str
    relative_path: str
    description: str = Field(default="", description="导出文件说明")
    editor_target: str = Field(default="", description="目标剪辑软件或交换格式")


class EditingExportPackage(BaseModel):
    package_name: str
    package_mode: str = Field(default="draft", description="导出包模式")
    status: str = Field(default="ready", description="导出状态")
    target_editor: str = Field(default="", description="目标剪辑软件范围")
    summary: str = Field(default="", description="导出摘要")
    files: list[ExportPackageFile] = Field(default_factory=list)
    missing_shot_nos: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EditingExportBundle(BaseModel):
    packages: list[EditingExportPackage] = Field(default_factory=list)


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
    generate_transition_images: bool = Field(default=False)
    assemble_episode_video: bool = Field(default=True)
    enable_multi_reference_images: bool = Field(default=True)
    enable_continuity_qc: bool = Field(default=True)
    max_continuity_retries: int = Field(default=1, ge=0, le=3)
    max_shot_segment_seconds: int = Field(default=6, ge=4, le=8)
    default_shot_overlap_seconds: float = Field(default=0.35, ge=0.0, le=1.5)
    render_role_image_limit: int = Field(default=2, ge=0, le=8)
    render_shot_limit: int = Field(default=1, ge=0, le=8)
    render_transition_limit: int = Field(default=2, ge=0, le=8)
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
    assembly_plan_path: str | None = None
    manifest_path: str
    generated_assets: list[GeneratedAsset] = Field(default_factory=list)
    stage_records: list[ProductionStageRecord] = Field(default_factory=list)
