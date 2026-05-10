from __future__ import annotations

from collections import defaultdict

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    AudioCue,
    AudioCueSheet,
    ContinuityChecklist,
    ContinuityChecklistItem,
    DeliveryChecklist,
    DeliveryChecklistItem,
    PropInventory,
    PropInventoryItem,
    ShortDramaPlan,
    ShotExecutionBeat,
    ShotExecutionSheet,
    SubtitleSegment,
    SubtitleTimeline,
)


COMMON_PROP_KEYWORDS = {
    "手机": "高",
    "信封": "高",
    "邀请函": "高",
    "照片": "高",
    "录音机": "高",
    "磁带": "高",
    "相机": "高",
    "钥匙": "中",
    "项链": "中",
    "戒指": "中",
    "面具": "高",
    "酒杯": "中",
    "手枪": "高",
    "刀": "高",
    "绳子": "中",
    "麦克风": "高",
    "台灯": "中",
    "旧信": "中",
    "纸条": "中",
}


class ExecutionDesignService:
    """补齐制作执行层细节。"""

    def build_shot_execution_sheet(self, plan: ShortDramaPlan) -> ShotExecutionSheet:
        beats: list[ShotExecutionBeat] = []
        for shot in plan.shots:
            duration = float(shot.duration_seconds)
            beat_ranges = [
                (0.0, round(duration * 0.3, 2), "建立信息", "主体入场或环境建立", "克制", "镜头先稳后进"),
                (round(duration * 0.3, 2), round(duration * 0.75, 2), "推进冲突", shot.summary, "升温", "让动作和表情成为中心"),
                (round(duration * 0.75, 2), duration, "留下钩子", shot.video_prompt, "悬停或爆发", "结尾动作要能无缝接到下镜头"),
            ]
            for beat_no, (start_s, end_s, focus, action, emotion, camera_note) in enumerate(beat_ranges, start=1):
                beats.append(
                    ShotExecutionBeat(
                        beat_no=beat_no,
                        shot_no=shot.shot_no,
                        start_seconds=start_s,
                        end_seconds=max(end_s, start_s),
                        focus=focus,
                        action=action,
                        emotion=emotion,
                        camera_note=camera_note,
                    )
                )
        return ShotExecutionSheet(beats=beats)

    def build_subtitle_timeline(self, plan: ShortDramaPlan) -> SubtitleTimeline:
        segments: list[SubtitleSegment] = []
        for shot in plan.shots:
            if not shot.subtitle_text:
                continue
            duration = float(shot.duration_seconds)
            start_s = 0.35
            end_s = max(start_s + 0.8, round(duration * 0.85, 2))
            segments.append(
                SubtitleSegment(
                    segment_no=len(segments) + 1,
                    shot_no=shot.shot_no,
                    start_seconds=start_s,
                    end_seconds=min(end_s, duration),
                    text=shot.subtitle_text,
                    emphasis="关键情绪词建议做轻微放大或加粗",
                    placement="bottom_center",
                    animation_style="fade_in_hold_fade_out",
                )
            )
        return SubtitleTimeline(segments=segments)

    def build_audio_cue_sheet(self, plan: ShortDramaPlan, assembly_plan: AssemblyPlan) -> AudioCueSheet:
        cues: list[AudioCue] = []
        current_time = 0.0
        for shot in plan.shots:
            duration = float(shot.duration_seconds)
            cues.append(
                AudioCue(
                    cue_no=len(cues) + 1,
                    shot_no=shot.shot_no,
                    cue_type="ambience",
                    start_seconds=round(current_time, 2),
                    end_seconds=round(current_time + duration, 2),
                    description=f"镜头{shot.shot_no} 环境底噪，需贴合《{shot.title}》气氛",
                    intensity="low",
                    sync_target="环境建立",
                )
            )
            cues.append(
                AudioCue(
                    cue_no=len(cues) + 1,
                    shot_no=shot.shot_no,
                    cue_type="accent",
                    start_seconds=round(current_time + duration * 0.75, 2),
                    end_seconds=round(current_time + min(duration, duration * 0.95), 2),
                    description=f"镜头{shot.shot_no} 情绪强调音或动作 hit",
                    intensity="medium",
                    sync_target="镜头结尾钩子",
                )
            )
            current_time += duration

        for transition in assembly_plan.transitions:
            cues.append(
                AudioCue(
                    cue_no=len(cues) + 1,
                    shot_no=None,
                    cue_type="transition",
                    start_seconds=0.0,
                    end_seconds=transition.duration_seconds,
                    description=f"转场{transition.transition_no} 音效：{transition.summary or transition.transition_type}",
                    intensity="medium",
                    sync_target=f"{transition.from_shot_no}->{transition.to_shot_no}",
                )
            )
        return AudioCueSheet(cues=cues)

    def build_continuity_checklist(self, plan: ShortDramaPlan) -> ContinuityChecklist:
        items: list[ContinuityChecklistItem] = []
        for shot in plan.shots:
            for category, description, method in (
                ("costume", "角色服装、发型、妆面是否与前后镜头一致", "对照角色手册和上一个镜头截图"),
                ("prop", "关键道具的位置、朝向、持握手是否连续", "逐帧核对首尾关键帧"),
                ("eyeline", "角色视线方向是否匹配对位关系", "检查对切镜头的视线轴"),
                ("lighting", "主光方向和色温是否延续场景气氛", "对比前后镜头高光与阴影分布"),
            ):
                items.append(
                    ContinuityChecklistItem(
                        item_no=len(items) + 1,
                        shot_no=shot.shot_no,
                        category=category,
                        description=f"镜头{shot.shot_no}：{description}",
                        check_method=method,
                        risk_level="medium",
                    )
                )
        return ContinuityChecklist(items=items)

    def build_prop_inventory(self, plan: ShortDramaPlan) -> PropInventory:
        prop_map: dict[str, set[int]] = defaultdict(set)
        for shot in plan.shots:
            text_blob = " ".join([shot.title, shot.summary, shot.first_frame_prompt, shot.video_prompt, shot.subtitle_text])
            for keyword in COMMON_PROP_KEYWORDS:
                if keyword in text_blob:
                    prop_map[keyword].add(shot.shot_no)

        items: list[PropInventoryItem] = []
        if not prop_map:
            items.append(
                PropInventoryItem(
                    prop_name="关键道具待人工确认",
                    used_in_shots=[shot.shot_no for shot in plan.shots],
                    continuity_note="当前提示词未稳定暴露明确道具，建议人工补充后再拍。",
                    visual_priority="high",
                )
            )
        else:
            for prop_name, used_in_shots in sorted(prop_map.items(), key=lambda item: min(item[1])):
                priority = COMMON_PROP_KEYWORDS.get(prop_name, "中")
                items.append(
                    PropInventoryItem(
                        prop_name=prop_name,
                        used_in_shots=sorted(used_in_shots),
                        continuity_note=f"{prop_name} 的位置、朝向和是否破损要在所有相关镜头中一致。",
                        visual_priority={"高": "high", "中": "medium"}.get(priority, "medium"),
                    )
                )
        return PropInventory(items=items)

    def build_delivery_checklist(self, plan: ShortDramaPlan, assembly_plan: AssemblyPlan) -> DeliveryChecklist:
        items = [
            DeliveryChecklistItem(
                item_no=1,
                stage="preproduction",
                description="故事圣经、角色手册、导演手册已人工复核",
                owner="director",
                done_definition="三份文件中的风格、人物和镜头意图不存在冲突",
            ),
            DeliveryChecklistItem(
                item_no=2,
                stage="generation",
                description="每个镜头至少有首帧图、视频提示词和字幕方案",
                owner="production",
                done_definition=f"当前应覆盖 {len(plan.shots)} 个镜头",
            ),
            DeliveryChecklistItem(
                item_no=3,
                stage="postproduction",
                description="转场、字幕、音频 cue 已落到装配清单",
                owner="editor",
                done_definition=f"装配方案中已有 {len(assembly_plan.transitions)} 个转场条目",
            ),
            DeliveryChecklistItem(
                item_no=4,
                stage="delivery",
                description="最终导出前检查 ffmpeg、镜头视频、音频和字幕时间轴是否齐全",
                owner="technical_director",
                done_definition="episode_assembly.json 标记 ready_to_concat 且所有资源存在",
            ),
        ]
        return DeliveryChecklist(items=items)
