from __future__ import annotations

import json
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import DramaProjectRequest
from projects.ai_short_drama.backend.app.services.drama_pipeline_service import DramaPipelineService


def test_placeholder_pipeline_runs_without_external_providers(tmp_path: Path, monkeypatch) -> None:
    request = DramaProjectRequest(
        project_name="占位全流程测试",
        premise="女记者用旧录像带追查三天后的死亡预告",
        style="都市悬疑",
        episode_goal="本地占位演练",
        role_count=2,
        shot_count=3,
        generate_role_images=True,
        generate_storyboard_images=True,
        generate_shot_videos=True,
        generate_transition_images=True,
        assemble_episode_video=True,
        use_placeholder_media=True,
        max_shot_segment_seconds=4,
        render_role_image_limit=2,
        render_shot_limit=3,
        render_transition_limit=2,
        project_id="placeholder-test",
    )

    def fail_external_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("占位模式不应初始化真实外部 provider")

    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.AgentTorchDramaTeamService",
        fail_external_provider,
    )
    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.NanobananaImageProvider",
        fail_external_provider,
    )
    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.SeedanceVideoProvider",
        fail_external_provider,
    )

    result = DramaPipelineService(tmp_path / "workspace").run(request)
    project_dir = Path(result.project_dir)

    assert (project_dir / "script" / "plan.json").is_file()
    assert (project_dir / "script" / "assembly_plan.json").is_file()
    assert (project_dir / "preproduction" / "story_bible.json").is_file()
    assert (project_dir / "preproduction" / "director_notebook.json").is_file()
    assert (project_dir / "preproduction" / "shot_segment_plan.json").is_file()
    assert (project_dir / "preproduction" / "subtitle_timeline.json").is_file()
    assert (project_dir / "preproduction" / "audio_cue_sheet.json").is_file()
    assert (project_dir / "preproduction" / "continuity_checklist.json").is_file()
    assert (project_dir / "roles" / "images" / "role_01.png").is_file()
    assert (project_dir / "storyboard" / "images" / "shot_01.png").is_file()
    assert (project_dir / "storyboard" / "end_frames" / "shot_01_end.png").is_file()
    placeholder_manifest = json.loads((project_dir / "logs" / "placeholder_media_manifest.json").read_text(encoding="utf-8"))
    shot_video_path = project_dir / placeholder_manifest["shot_video_paths"][0]
    segment_video_paths = sorted((project_dir / "video" / "segments").glob("shot_01_seg_01.*"))
    assert segment_video_paths
    assert segment_video_paths[0].is_file()
    assert (project_dir / "video" / "frames" / "shot_01_seg_01_tail.png").is_file()
    assert shot_video_path.is_file()
    assert shot_video_path.suffix in {".mp4", ".avi"}
    assert (project_dir / "video" / "transitions" / "transition_01.png").is_file()
    assert (project_dir / "logs" / "continuity_report.json").is_file()
    assert (project_dir / "logs" / "placeholder_media_manifest.json").is_file()
    assert (project_dir / "exports" / "episode_assembly.json").is_file()
    assert (project_dir / "exports" / "episode_preview.mp4").is_file() or (project_dir / "exports" / "episode_preview_placeholder.avi").is_file()
    assert (project_dir / "exports" / "editing_export_bundle.json").is_file()
    assert (project_dir / "subtitles" / "captions_draft.srt").is_file()
    assert (project_dir / "subtitles" / "captions_final.srt").is_file()
    assert (project_dir / "exports" / "draft" / "timeline_draft.fcpxml").is_file()
    assert (project_dir / "exports" / "final" / "timeline_final.fcpxml").is_file()

    manifest = json.loads((project_dir / "logs" / "manifest.json").read_text(encoding="utf-8"))
    stage_names = {stage["stage_name"] for stage in manifest["stage_records"]}
    assert "placeholder_planning" in stage_names
    assert "placeholder_shot_generation" in stage_names
    assert any(asset["metadata"].get("placeholder_media") for asset in manifest["generated_assets"])
    assert any(stage["stage_name"] == "episode_assembly" and stage["status"] == "completed" for stage in manifest["stage_records"])

    export_bundle = json.loads((project_dir / "exports" / "editing_export_bundle.json").read_text(encoding="utf-8"))
    assert export_bundle["packages"][0]["package_mode"] == "draft"
    assert export_bundle["packages"][1]["package_mode"] == "final"
    assert export_bundle["packages"][1]["status"] == "ready"

    assembly = json.loads((project_dir / "exports" / "episode_assembly.json").read_text(encoding="utf-8"))
    assert assembly["assembly_status"] in {"ready_to_concat", "placeholder_preview"}
