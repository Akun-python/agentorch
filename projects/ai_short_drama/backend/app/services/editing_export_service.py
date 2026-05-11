from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    AudioCueSheet,
    EditingExportBundle,
    EditingExportPackage,
    ExportPackageFile,
    GeneratedAsset,
    ProductionStageRecord,
    ShortDramaPlan,
    SubtitleSegment,
    SubtitleTimeline,
)
from projects.ai_short_drama.backend.app.repositories import ProjectRepository


FCPXML_FORMAT_ID = "r1"
FCPXML_SEQUENCE_FORMAT_ID = "r2"
FCPXML_EVENT_NAME = "AI短剧导出"


@dataclass(slots=True)
class TimelineShot:
    shot_no: int
    title: str
    start_seconds: float
    duration_seconds: float
    media_path: Path | None
    has_media: bool


@dataclass(slots=True)
class AudioCueTrack:
    cue_no: int
    cue_type: str
    cue_name: str
    start_seconds: float
    duration_seconds: float
    asset_id: str
    asset_path: Path
    lane: int


class EditingExportService:
    """输出开放格式工程包，供剪映字幕导入和专业剪辑软件时间线导入使用。"""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def build_export_bundle(
        self,
        *,
        project_id: str,
        project_dir: Path,
        plan: ShortDramaPlan,
        assembly_plan: AssemblyPlan,
        subtitle_timeline: SubtitleTimeline,
        audio_cue_sheet: AudioCueSheet,
        shot_video_paths: list[Path],
    ) -> tuple[EditingExportBundle, list[GeneratedAsset], ProductionStageRecord]:
        shot_path_map = self._build_shot_path_map(shot_video_paths)
        timeline_shots = self._build_timeline_shots(plan=plan, shot_path_map=shot_path_map)
        cue_tracks = self._build_audio_placeholder_tracks(project_id=project_id, audio_cue_sheet=audio_cue_sheet)
        packages: list[EditingExportPackage] = []
        assets: list[GeneratedAsset] = []

        # 先导出 draft 包，保证没有视频也能审稿和导入字幕。
        draft_mode = "draft"
        draft_export_dir = self.repository.export_path(project_id, draft_mode)
        draft_export_dir.mkdir(parents=True, exist_ok=True)
        draft_subtitle_path = self.repository.subtitle_path(project_id, "captions_draft.srt")
        draft_subtitle_path.write_text(self._build_srt_content(subtitle_timeline.segments, timeline_shots), encoding="utf-8")
        draft_fcpxml_path = draft_export_dir / "timeline_draft.fcpxml"
        draft_fcpxml_path.write_text(
            self._build_fcpxml_content(
                package_name=f"{plan.project_title}-draft",
                timeline_shots=timeline_shots,
                cue_tracks=cue_tracks,
                subtitle_timeline=subtitle_timeline,
                assembly_plan=assembly_plan,
                include_media=False,
            ),
            encoding="utf-8",
        )
        draft_media_manifest_path = draft_export_dir / "media_manifest_draft.json"
        draft_media_manifest_path.write_text(
            json.dumps(
                self._build_media_manifest_payload(
                    project_dir=project_dir,
                    timeline_shots=timeline_shots,
                    cue_tracks=cue_tracks,
                    subtitle_timeline=subtitle_timeline,
                    audio_cue_sheet=audio_cue_sheet,
                    assembly_plan=assembly_plan,
                    include_media=False,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        draft_package = EditingExportPackage(
            package_name=f"{plan.project_title}-draft",
            package_mode=draft_mode,
            status="ready",
            target_editor="capcut_subtitle_and_fcpxml",
            summary="骨架导出包，适合先导字幕、审查镜头顺序和缺失素材。",
            files=[
                ExportPackageFile(
                    asset_type="subtitle_srt",
                    relative_path=str(draft_subtitle_path.relative_to(project_dir)),
                    description="CapCut 桌面/Web 可直接导入的字幕文件",
                    editor_target="CapCut",
                ),
                ExportPackageFile(
                    asset_type="timeline_fcpxml",
                    relative_path=str(draft_fcpxml_path.relative_to(project_dir)),
                    description="专业剪辑软件可读取的骨架时间线",
                    editor_target="Premiere/Resolve/FCP",
                ),
                ExportPackageFile(
                    asset_type="media_manifest",
                    relative_path=str(draft_media_manifest_path.relative_to(project_dir)),
                    description="骨架时间线的素材占位清单",
                    editor_target="All",
                ),
                ExportPackageFile(
                    asset_type="audio_placeholders",
                    relative_path="audio/placeholders/",
                    description="音频 cue 的静音占位轨目录",
                    editor_target="All",
                ),
            ],
            missing_shot_nos=[shot.shot_no for shot in timeline_shots if not shot.has_media],
            notes=[
                "draft 包允许镜头视频缺失。",
                "字幕以现有 subtitle_timeline.json 为准。",
                f"音频 cue 条目数：{len(audio_cue_sheet.cues)}。",
            ],
        )
        draft_manifest_path = draft_export_dir / "export_manifest.json"
        draft_package.files.append(
            ExportPackageFile(
                asset_type="export_manifest",
                relative_path=str(draft_manifest_path.relative_to(project_dir)),
                description="draft 导出包清单",
                editor_target="All",
            )
        )
        draft_manifest_path.write_text(draft_package.model_dump_json(indent=2), encoding="utf-8")
        packages.append(draft_package)
        assets.extend(
            self._package_to_assets(
                package=draft_package,
                source_name=assembly_plan.episode_title,
            )
        )

        # final 包只有在镜头素材齐全时标记 ready，否则标记 blocked 并写清缺失项。
        final_mode = "final"
        final_export_dir = self.repository.export_path(project_id, final_mode)
        final_export_dir.mkdir(parents=True, exist_ok=True)
        final_subtitle_path = self.repository.subtitle_path(project_id, "captions_final.srt")
        final_subtitle_path.write_text(self._build_srt_content(subtitle_timeline.segments, timeline_shots), encoding="utf-8")
        final_fcpxml_path = final_export_dir / "timeline_final.fcpxml"
        final_media_manifest_path = final_export_dir / "media_manifest_final.json"
        final_media_manifest_path.write_text(
            json.dumps(
                self._build_media_manifest_payload(
                    project_dir=project_dir,
                    timeline_shots=timeline_shots,
                    cue_tracks=cue_tracks,
                    subtitle_timeline=subtitle_timeline,
                    audio_cue_sheet=audio_cue_sheet,
                    assembly_plan=assembly_plan,
                    include_media=True,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        final_status = "ready" if all(shot.has_media for shot in timeline_shots) else "blocked"
        final_notes = [
            "final 包要求镜头视频实际存在，FCPXML 会直接引用本地绝对路径。",
            f"转场条目数：{len(assembly_plan.transitions)}。",
            f"音频 cue 条目数：{len(audio_cue_sheet.cues)}。",
        ]
        final_files = [
            ExportPackageFile(
                asset_type="subtitle_srt",
                relative_path=str(final_subtitle_path.relative_to(project_dir)),
                description="正式字幕文件",
                editor_target="CapCut",
            ),
            ExportPackageFile(
                asset_type="media_manifest",
                relative_path=str(final_media_manifest_path.relative_to(project_dir)),
                description="正式时间线素材索引",
                editor_target="All",
            ),
            ExportPackageFile(
                asset_type="audio_placeholders",
                relative_path="audio/placeholders/",
                description="音频 cue 的静音占位轨目录",
                editor_target="All",
            ),
        ]
        if final_status == "ready":
            final_fcpxml_path.write_text(
                self._build_fcpxml_content(
                    package_name=f"{plan.project_title}-final",
                    timeline_shots=timeline_shots,
                    cue_tracks=cue_tracks,
                    subtitle_timeline=subtitle_timeline,
                    assembly_plan=assembly_plan,
                    include_media=True,
                ),
                encoding="utf-8",
            )
            final_files.append(
                ExportPackageFile(
                    asset_type="timeline_fcpxml",
                    relative_path=str(final_fcpxml_path.relative_to(project_dir)),
                    description="正式时间线交换文件",
                    editor_target="Premiere/Resolve/FCP",
                )
            )
        if final_status == "blocked":
            if final_fcpxml_path.exists():
                final_fcpxml_path.unlink()
            final_notes.append("存在缺失镜头视频，需补齐后再导入正式时间线。")
        final_package = EditingExportPackage(
            package_name=f"{plan.project_title}-final",
            package_mode=final_mode,
            status=final_status,
            target_editor="fcpxml_timeline",
            summary="完整导出包，适合专业剪辑软件直接导入时间线。",
            files=final_files,
            missing_shot_nos=[shot.shot_no for shot in timeline_shots if not shot.has_media],
            notes=final_notes,
        )
        final_manifest_path = final_export_dir / "export_manifest.json"
        final_package.files.append(
            ExportPackageFile(
                asset_type="export_manifest",
                relative_path=str(final_manifest_path.relative_to(project_dir)),
                description="final 导出包清单",
                editor_target="All",
            )
        )
        final_manifest_path.write_text(final_package.model_dump_json(indent=2), encoding="utf-8")
        packages.append(final_package)
        assets.extend(
            self._package_to_assets(
                package=final_package,
                source_name=assembly_plan.episode_title,
            )
        )

        bundle = EditingExportBundle(packages=packages)
        bundle_path = self.repository.export_path(project_id, "editing_export_bundle.json")
        bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        assets.append(
            GeneratedAsset(
                asset_type="editing_export_bundle",
                relative_path=str(bundle_path.relative_to(project_dir)),
                source_name=assembly_plan.episode_title,
                metadata={"package_count": len(packages)},
            )
        )

        stage_status = "completed" if final_status == "ready" else "partial"
        stage_detail = "已输出 draft/final 开放格式工程包" if final_status == "ready" else "已输出 draft/final 工程包，final 仍有缺失镜头"
        stage_record = ProductionStageRecord(
            stage_name="editing_export",
            status=stage_status,
            detail=stage_detail,
            metadata={
                "bundle_path": str(bundle_path),
                "draft_status": draft_package.status,
                "final_status": final_package.status,
                "missing_shot_nos": final_package.missing_shot_nos,
            },
        )
        return bundle, assets, stage_record

    @staticmethod
    def _build_shot_path_map(shot_video_paths: list[Path]) -> dict[int, Path]:
        path_map: dict[int, Path] = {}
        for path in shot_video_paths:
            stem = path.stem
            digits = "".join(ch for ch in stem if ch.isdigit())
            if digits:
                path_map[int(digits)] = path
        return path_map

    @staticmethod
    def _build_timeline_shots(*, plan: ShortDramaPlan, shot_path_map: dict[int, Path]) -> list[TimelineShot]:
        timeline_shots: list[TimelineShot] = []
        current_time = 0.0
        for shot in plan.shots:
            media_path = shot_path_map.get(shot.shot_no)
            has_media = bool(media_path and media_path.is_file())
            timeline_shots.append(
                TimelineShot(
                    shot_no=shot.shot_no,
                    title=shot.title,
                    start_seconds=round(current_time, 3),
                    duration_seconds=float(shot.duration_seconds),
                    media_path=media_path,
                    has_media=has_media,
                )
            )
            current_time += float(shot.duration_seconds)
        return timeline_shots

    @staticmethod
    def _build_srt_content(segments: list[SubtitleSegment], timeline_shots: list[TimelineShot]) -> str:
        shot_start_map = {shot.shot_no: shot.start_seconds for shot in timeline_shots}
        blocks: list[str] = []
        for index, segment in enumerate(segments, start=1):
            shot_start = shot_start_map.get(segment.shot_no, 0.0)
            start_seconds = max(0.0, shot_start + segment.start_seconds)
            end_seconds = max(start_seconds, shot_start + segment.end_seconds)
            blocks.append(
                "\n".join(
                    [
                        str(index),
                        f"{EditingExportService._format_srt_time(start_seconds)} --> {EditingExportService._format_srt_time(end_seconds)}",
                        segment.text,
                    ]
                )
            )
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        total_milliseconds = int(round(max(0.0, seconds) * 1000))
        hours, remainder = divmod(total_milliseconds, 3600 * 1000)
        minutes, remainder = divmod(remainder, 60 * 1000)
        secs, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _build_fcpxml_content(
        self,
        *,
        package_name: str,
        timeline_shots: list[TimelineShot],
        cue_tracks: list[AudioCueTrack],
        subtitle_timeline: SubtitleTimeline,
        assembly_plan: AssemblyPlan,
        include_media: bool,
    ) -> str:
        root = Element("fcpxml", version="1.11")
        resources = SubElement(root, "resources")
        SubElement(resources, "format", id=FCPXML_FORMAT_ID, name="FFVideoFormat1080p30", frameDuration="1/30s", width="1920", height="1080")
        SubElement(resources, "format", id=FCPXML_SEQUENCE_FORMAT_ID, name="FFVideoFormat1080p30", frameDuration="1/30s", width="1920", height="1080")

        asset_id_map: dict[int, str] = {}
        for asset_index, shot in enumerate(timeline_shots, start=1):
            asset_id = f"asset{asset_index}"
            asset_id_map[shot.shot_no] = asset_id
            media_path = shot.media_path.resolve().as_uri() if include_media and shot.has_media and shot.media_path else f"placeholder://shot/{shot.shot_no}"
            SubElement(
                resources,
                "asset",
                id=asset_id,
                name=shot.title,
                src=media_path,
                hasVideo="1",
                hasAudio="0",
                format=FCPXML_FORMAT_ID,
                duration=self._seconds_to_fcpxml_time(shot.duration_seconds),
            )
        for cue_track in cue_tracks:
            SubElement(
                resources,
                "asset",
                id=cue_track.asset_id,
                name=cue_track.cue_name,
                src=cue_track.asset_path.resolve().as_uri(),
                hasVideo="0",
                hasAudio="1",
                audioSources="1",
                audioChannels="1",
                duration=self._seconds_to_fcpxml_time(cue_track.duration_seconds),
            )

        library = SubElement(root, "library")
        event = SubElement(library, "event", name=FCPXML_EVENT_NAME)
        project = SubElement(event, "project", name=package_name)
        sequence = SubElement(
            project,
            "sequence",
            format=FCPXML_SEQUENCE_FORMAT_ID,
            duration=self._seconds_to_fcpxml_time(sum(shot.duration_seconds for shot in timeline_shots)),
            tcStart="0s",
            tcFormat="NDF",
        )
        spine = SubElement(sequence, "spine")
        subtitle_map = self._group_subtitles_by_shot(subtitle_timeline)
        transition_map = {
            transition.from_shot_no: transition
            for transition in assembly_plan.transitions
        }
        for shot in timeline_shots:
            clip = SubElement(
                spine,
                "asset-clip",
                name=shot.title,
                ref=asset_id_map[shot.shot_no],
                offset=self._seconds_to_fcpxml_time(shot.start_seconds),
                start="0s",
                duration=self._seconds_to_fcpxml_time(shot.duration_seconds),
            )
            for segment in subtitle_map.get(shot.shot_no, []):
                SubElement(
                    clip,
                    "title",
                    name=f"字幕{segment.segment_no}",
                    lane="1",
                    offset=self._seconds_to_fcpxml_time(segment.start_seconds),
                    start="0s",
                    duration=self._seconds_to_fcpxml_time(max(0.0, segment.end_seconds - segment.start_seconds)),
                ).text = segment.text
            transition = transition_map.get(shot.shot_no)
            if transition:
                SubElement(
                    clip,
                    "marker",
                    start=self._seconds_to_fcpxml_time(max(0.0, shot.duration_seconds - min(transition.duration_seconds, shot.duration_seconds))),
                    duration=self._seconds_to_fcpxml_time(transition.duration_seconds),
                    value=f"转场{transition.transition_no}",
                    note=transition.summary or transition.transition_type,
                )
        for cue_track in cue_tracks:
            SubElement(
                spine,
                "asset-clip",
                name=cue_track.cue_name,
                ref=cue_track.asset_id,
                offset=self._seconds_to_fcpxml_time(cue_track.start_seconds),
                start="0s",
                duration=self._seconds_to_fcpxml_time(cue_track.duration_seconds),
                lane=str(-cue_track.lane),
                role=self._cue_role(cue_track.cue_type),
            )
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + tostring(root, encoding="unicode")

    @staticmethod
    def _group_subtitles_by_shot(subtitle_timeline: SubtitleTimeline) -> dict[int, list[SubtitleSegment]]:
        grouped: dict[int, list[SubtitleSegment]] = {}
        for segment in subtitle_timeline.segments:
            grouped.setdefault(segment.shot_no, []).append(segment)
        return grouped

    @staticmethod
    def _seconds_to_fcpxml_time(seconds: float) -> str:
        fraction = Fraction(max(0.0, seconds)).limit_denominator(30000)
        return f"{fraction.numerator}/{fraction.denominator}s"

    def _build_media_manifest_payload(
        self,
        *,
        project_dir: Path,
        timeline_shots: list[TimelineShot],
        cue_tracks: list[AudioCueTrack],
        subtitle_timeline: SubtitleTimeline,
        audio_cue_sheet: AudioCueSheet,
        assembly_plan: AssemblyPlan,
        include_media: bool,
    ) -> dict:
        subtitles_by_shot = self._group_subtitles_by_shot(subtitle_timeline)
        transitions_by_shot = {transition.from_shot_no: transition for transition in assembly_plan.transitions}
        return {
            "include_media": include_media,
            "shots": [
                {
                    "shot_no": shot.shot_no,
                    "title": shot.title,
                    "start_seconds": shot.start_seconds,
                    "duration_seconds": shot.duration_seconds,
                    "has_media": shot.has_media,
                    "media_path": self._relative_media_path(project_dir=project_dir, media_path=shot.media_path) if include_media and shot.media_path else "",
                    "media_uri": shot.media_path.resolve().as_uri() if include_media and shot.media_path and shot.has_media else "",
                    "subtitle_count": len(subtitles_by_shot.get(shot.shot_no, [])),
                    "transition_to_next": (
                        {
                            "transition_type": transitions_by_shot[shot.shot_no].transition_type,
                            "duration_seconds": transitions_by_shot[shot.shot_no].duration_seconds,
                            "summary": transitions_by_shot[shot.shot_no].summary,
                        }
                        if shot.shot_no in transitions_by_shot
                        else None
                    ),
                }
                for shot in timeline_shots
            ],
            "audio_placeholder_tracks": [
                {
                    "cue_no": cue_track.cue_no,
                    "cue_type": cue_track.cue_type,
                    "cue_name": cue_track.cue_name,
                    "start_seconds": cue_track.start_seconds,
                    "duration_seconds": cue_track.duration_seconds,
                    "asset_path": self._relative_media_path(project_dir=project_dir, media_path=cue_track.asset_path),
                    "lane": cue_track.lane,
                }
                for cue_track in cue_tracks
            ],
            "audio_cues": [cue.model_dump() for cue in audio_cue_sheet.cues],
        }

    @staticmethod
    def _relative_media_path(*, project_dir: Path, media_path: Path) -> str:
        return str(media_path.resolve().relative_to(project_dir.resolve()))

    def _build_audio_placeholder_tracks(self, *, project_id: str, audio_cue_sheet: AudioCueSheet) -> list[AudioCueTrack]:
        tracks: list[AudioCueTrack] = []
        for cue in audio_cue_sheet.cues:
            duration_seconds = max(0.3, round(cue.end_seconds - cue.start_seconds, 3))
            asset_path = self.repository.audio_placeholder_path(project_id, cue.cue_no, cue.cue_type)
            self._write_silent_wav(asset_path, duration_seconds=duration_seconds)
            tracks.append(
                AudioCueTrack(
                    cue_no=cue.cue_no,
                    cue_type=cue.cue_type,
                    cue_name=f"cue_{cue.cue_no:03d}_{cue.cue_type}",
                    start_seconds=cue.start_seconds,
                    duration_seconds=duration_seconds,
                    asset_id=f"audio_cue_{cue.cue_no:03d}",
                    asset_path=asset_path,
                    lane=1 if cue.cue_type in {"dialogue", "voice"} else 2,
                )
            )
        return tracks

    @staticmethod
    def _write_silent_wav(output_path: Path, *, duration_seconds: float, sample_rate: int = 48000) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame_count = max(1, int(duration_seconds * sample_rate))
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count)

    @staticmethod
    def _cue_role(cue_type: str) -> str:
        if cue_type in {"dialogue", "voice"}:
            return "dialogue"
        if cue_type in {"music", "score"}:
            return "music"
        return "effects"

    @staticmethod
    def _package_to_assets(
        *,
        package: EditingExportPackage,
        source_name: str,
    ) -> list[GeneratedAsset]:
        assets: list[GeneratedAsset] = []
        for file in package.files:
            assets.append(
                GeneratedAsset(
                    asset_type=f"{package.package_mode}_{file.asset_type}",
                    relative_path=file.relative_path,
                    source_name=source_name,
                    metadata={
                        "package_mode": package.package_mode,
                        "editor_target": file.editor_target,
                        "status": package.status,
                    },
                )
            )
        return assets
