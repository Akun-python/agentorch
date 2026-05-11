from __future__ import annotations

from collections import defaultdict
from math import ceil

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
    ShotSegmentPlanItem,
    ShotSegmentPlanSheet,
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

    def build_shot_segment_plan(self, plan: ShortDramaPlan, *, max_segment_seconds: int = 6) -> ShotSegmentPlanSheet:
        segments: list[ShotSegmentPlanItem] = []
        segment_limit = max(4, min(8, int(max_segment_seconds)))
        for shot in plan.shots:
            total_duration = max(4, min(15, int(round(float(shot.duration_seconds)))))
            max_possible_segments = max(1, total_duration // 4)
            segment_count = max(1, min(ceil(total_duration / segment_limit), max_possible_segments))
            base_duration = total_duration // segment_count
            remainder = total_duration % segment_count
            current_time = 0.0
            for segment_no in range(1, segment_count + 1):
                segment_duration = base_duration + (1 if segment_no <= remainder else 0)
                start_seconds = round(current_time, 2)
                end_seconds = round(current_time + segment_duration, 2)
                current_time = end_seconds
                if segment_no == 1:
                    prompt_focus = f"建立《{shot.title}》的起始空间和人物动作"
                elif segment_no == segment_count:
                    prompt_focus = f"把动作推到尾帧目标：{shot.end_frame_prompt}"
                else:
                    prompt_focus = f"推进《{shot.title}》中段动作，避免人物和道具突变"
                segments.append(
                    ShotSegmentPlanItem(
                        shot_no=shot.shot_no,
                        segment_no=segment_no,
                        segment_count=segment_count,
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        duration_seconds=segment_duration,
                        prompt_focus=prompt_focus,
                        continuity_goal="；".join(shot.continuity_notes),
                        target_end_frame=shot.end_frame_prompt,
                    )
                )
        return ShotSegmentPlanSheet(segments=segments)

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
        shot_start_map: dict[int, float] = {}
        for shot_index, shot in enumerate(plan.shots):
            shot_start_map[shot.shot_no] = round(current_time, 2)
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
            if shot_index < len(plan.shots) - 1:
                cues.append(
                    AudioCue(
                        cue_no=len(cues) + 1,
                        shot_no=shot.shot_no,
                        cue_type="audio_bridge",
                        start_seconds=round(current_time + max(0.0, duration - 0.45), 2),
                        end_seconds=round(current_time + duration + 0.35, 2),
                        description=f"镜头{shot.shot_no} 尾部环境声延续到下一镜，避免声音硬断",
                        intensity="low",
                        sync_target="镜头边界连续",
                    )
                )
            current_time += duration

        for transition in assembly_plan.transitions:
            cues.append(
                AudioCue(
                    cue_no=len(cues) + 1,
                    shot_no=None,
                    cue_type="transition",
                    start_seconds=round(
                        shot_start_map.get(transition.from_shot_no, 0.0)
                        + max(0.0, float(next((shot.duration_seconds for shot in plan.shots if shot.shot_no == transition.from_shot_no), 0.0)) - transition.duration_seconds),
                        2,
                    ),
                    end_seconds=round(
                        shot_start_map.get(transition.from_shot_no, 0.0)
                        + float(next((shot.duration_seconds for shot in plan.shots if shot.shot_no == transition.from_shot_no), 0.0)),
                        2,
                    ),
                    description=f"转场{transition.transition_no} 音效：{transition.summary or transition.transition_type}",
                    intensity="medium",
                    sync_target=f"{transition.from_shot_no}->{transition.to_shot_no}",
                )
            )
            cues.append(
                AudioCue(
                    cue_no=len(cues) + 1,
                    shot_no=None,
                    cue_type="transition_audio_bridge",
                    start_seconds=round(
                        shot_start_map.get(transition.from_shot_no, 0.0)
                        + max(
                            0.0,
                            float(next((shot.duration_seconds for shot in plan.shots if shot.shot_no == transition.from_shot_no), 0.0))
                            - max(transition.duration_seconds, transition.overlap_seconds),
                        ),
                        2,
                    ),
                    end_seconds=round(
                        shot_start_map.get(transition.from_shot_no, 0.0)
                        + float(next((shot.duration_seconds for shot in plan.shots if shot.shot_no == transition.from_shot_no), 0.0))
                        + transition.overlap_seconds,
                        2,
                    ),
                    description=f"转场{transition.transition_no} 音频桥：{transition.audio_bridge}",
                    intensity="medium",
                    sync_target=f"{transition.from_shot_no}->{transition.to_shot_no} overlap {transition.overlap_seconds}s",
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
                ("camera_axis", shot.camera_axis.axis_description, "检查主体运动方向和机位轴线是否突然反转"),
                (
                    "end_frame",
                    f"尾帧必须接近目标：{shot.end_frame_prompt}",
                    "对照生成尾帧、目标尾帧图和下一镜头首帧",
                ),
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
            for character in shot.character_state:
                items.append(
                    ContinuityChecklistItem(
                        item_no=len(items) + 1,
                        shot_no=shot.shot_no,
                        category="character_state",
                        description=(
                            f"镜头{shot.shot_no}：{character.name} 站位={character.blocking}；"
                            f"姿态={character.pose}；视线={character.eyeline}；服装={character.wardrobe_state}"
                        ),
                        check_method="对照角色立绘、上一镜尾帧和当前镜头尾帧",
                        risk_level="high",
                    )
                )
            for prop in shot.prop_state:
                items.append(
                    ContinuityChecklistItem(
                        item_no=len(items) + 1,
                        shot_no=shot.shot_no,
                        category="prop_state",
                        description=(
                            f"镜头{shot.shot_no}：{prop.prop_name} 位置={prop.placement}；"
                            f"朝向={prop.orientation}；手位={prop.hand_usage}"
                        ),
                        check_method="对照分镜图、尾帧和道具清单",
                        risk_level="high" if prop.continuity_priority == "high" else "medium",
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
                stage="generation",
                description="连续性尾帧、分段视频和质检报告已生成",
                owner="technical_director",
                done_definition="video/frames、video/segments、video/qc 和 logs/continuity_report.json 可被追溯",
            ),
            DeliveryChecklistItem(
                item_no=5,
                stage="delivery",
                description="最终导出前检查 ffmpeg、镜头视频、音频和字幕时间轴是否齐全",
                owner="technical_director",
                done_definition="episode_assembly.json 标记 ready_to_concat 且所有资源存在",
            ),
        ]
        return DeliveryChecklist(items=items)
