from __future__ import annotations

import json
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    AudioCueSheet,
    RoleCard,
    ShortDramaPlan,
    ShotPlan,
    SubtitleSegment,
    SubtitleTimeline,
    TransitionPlan,
)
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.services.editing_export_service import EditingExportService


def _build_plan() -> ShortDramaPlan:
    return ShortDramaPlan(
        project_title="导出测试短剧",
        logline="测试导出链路",
        visual_style="悬疑",
        episode_summary="两镜头测试",
        roles=[
            RoleCard(
                name="林夏",
                appearance="黑色风衣",
                personality="冷静敏锐",
                relationship="主角",
                avatar_prompt="都市悬疑女记者",
                voice_style="克制低沉",
            )
        ],
        shots=[
            ShotPlan(
                shot_no=1,
                title="镜头一",
                summary="女主推门进入旧档案室",
                duration_seconds=4,
                ratio="16:9",
                first_frame_prompt="旧档案室入口",
                video_prompt="推镜进入档案室",
                subtitle_text="门开了。",
                focus_roles=["林夏"],
            ),
            ShotPlan(
                shot_no=2,
                title="镜头二",
                summary="她在档案柜前发现匿名信",
                duration_seconds=5,
                ratio="16:9",
                first_frame_prompt="档案柜特写",
                video_prompt="手持镜头靠近匿名信",
                subtitle_text="这封信不对劲。",
                focus_roles=["林夏"],
            ),
        ],
    )


def _build_subtitle_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
        segments=[
            SubtitleSegment(
                segment_no=1,
                shot_no=1,
                start_seconds=0.35,
                end_seconds=3.2,
                text="门开了。",
            ),
            SubtitleSegment(
                segment_no=2,
                shot_no=2,
                start_seconds=0.4,
                end_seconds=4.5,
                text="这封信不对劲。",
            ),
        ]
    )


def _build_assembly_plan() -> AssemblyPlan:
    return AssemblyPlan(
        episode_title="导出测试短剧-第一集",
        editing_style="快节奏",
        transitions=[
            TransitionPlan(
                transition_no=1,
                from_shot_no=1,
                to_shot_no=2,
                transition_type="flash",
                duration_seconds=0.5,
                visual_prompt="强闪切入第二镜头",
                summary="情绪闪切",
            )
        ],
        final_runtime_seconds=9.5,
        export_notes=["保留悬疑气氛"],
    )


def _build_audio_cue_sheet() -> AudioCueSheet:
    return AudioCueSheet(cues=[])


def test_format_srt_time_and_utf8_content() -> None:
    assert EditingExportService._format_srt_time(0.35) == "00:00:00,350"
    assert EditingExportService._format_srt_time(65.432) == "00:01:05,432"


def test_export_bundle_supports_draft_without_videos(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    repository = ProjectRepository(project_root)
    service = EditingExportService(repository)
    project_dir = repository.ensure_project_layout("proj-draft")

    bundle, assets, stage = service.build_export_bundle(
        project_id="proj-draft",
        project_dir=project_dir,
        plan=_build_plan(),
        assembly_plan=_build_assembly_plan(),
        subtitle_timeline=_build_subtitle_timeline(),
        audio_cue_sheet=_build_audio_cue_sheet(),
        shot_video_paths=[],
    )

    assert stage.status == "partial"
    assert len(bundle.packages) == 2
    assert bundle.packages[0].package_mode == "draft"
    assert bundle.packages[0].status == "ready"
    assert bundle.packages[1].package_mode == "final"
    assert bundle.packages[1].status == "blocked"
    assert bundle.packages[1].missing_shot_nos == [1, 2]
    assert (project_dir / "subtitles" / "captions_draft.srt").is_file()
    assert (project_dir / "exports" / "draft" / "timeline_draft.fcpxml").is_file()
    assert (project_dir / "exports" / "editing_export_bundle.json").is_file()
    assert any(asset.asset_type == "editing_export_bundle" for asset in assets)


def test_export_bundle_generates_final_timeline_with_media_and_xml_escape(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    repository = ProjectRepository(project_root)
    service = EditingExportService(repository)
    project_dir = repository.ensure_project_layout("proj-final")

    shot_1 = repository.shot_video_path("proj-final", 1)
    shot_2 = repository.shot_video_path("proj-final", 2)
    shot_1.parent.mkdir(parents=True, exist_ok=True)
    shot_1.write_bytes(b"fake-mp4-1")
    shot_2.write_bytes(b"fake-mp4-2")

    subtitle_timeline = SubtitleTimeline(
        segments=[
            SubtitleSegment(
                segment_no=1,
                shot_no=1,
                start_seconds=0.2,
                end_seconds=2.8,
                text="她说：<别回头> & 继续走",
            )
        ]
    )

    bundle, _, stage = service.build_export_bundle(
        project_id="proj-final",
        project_dir=project_dir,
        plan=_build_plan(),
        assembly_plan=_build_assembly_plan(),
        subtitle_timeline=subtitle_timeline,
        audio_cue_sheet=_build_audio_cue_sheet(),
        shot_video_paths=[shot_1, shot_2],
    )

    assert stage.status == "completed"
    assert bundle.packages[1].status == "ready"
    final_fcpxml = (project_dir / "exports" / "final" / "timeline_final.fcpxml").read_text(encoding="utf-8")
    assert "placeholder://" not in final_fcpxml
    assert "&lt;别回头&gt;" in final_fcpxml
    assert "&amp; 继续走" in final_fcpxml
    assert shot_1.resolve().as_uri() in final_fcpxml

    final_manifest = json.loads((project_dir / "exports" / "final" / "media_manifest_final.json").read_text(encoding="utf-8"))
    assert final_manifest["include_media"] is True
    assert final_manifest["shots"][0]["has_media"] is True
