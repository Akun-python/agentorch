from __future__ import annotations

import json
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import AssemblyPlan, DramaProjectRequest, RoleCard, ShortDramaPlan, ShotPlan
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


def test_pipeline_uses_real_planning_and_images_but_placeholder_videos(tmp_path: Path, monkeypatch) -> None:
    request = DramaProjectRequest(
        project_name="真实规划图片占位视频测试",
        premise="女记者追查录像带预告",
        style="都市悬疑",
        episode_goal="只跳过 Seedance",
        role_count=1,
        shot_count=1,
        generate_role_images=True,
        generate_storyboard_images=True,
        generate_shot_videos=True,
        generate_transition_images=False,
        assemble_episode_video=True,
        use_placeholder_media=False,
        use_placeholder_videos=True,
        max_continuity_retries=0,
        render_role_image_limit=1,
        render_shot_limit=1,
        project_id="placeholder-video-only-test",
    )
    calls = {"agent": 0, "image": 0, "seedance": 0}
    plan = ShortDramaPlan(
        project_title="真实规划图片占位视频测试",
        logline="测试只跳过视频生成",
        visual_style="都市悬疑",
        episode_summary="首镜测试",
        roles=[
            RoleCard(
                name="林夏",
                appearance="深色风衣",
                personality="冷静",
                relationship="主角",
                avatar_prompt="真实角色图提示词",
                voice_style="克制",
            )
        ],
        shots=[
            ShotPlan(
                shot_no=1,
                title="真实分镜占位视频",
                summary="主角看见录像带",
                duration_seconds=4,
                ratio="16:9",
                first_frame_prompt="真实首帧提示词",
                end_frame_prompt="真实尾帧提示词",
                video_prompt="这段不应发给 Seedance，只用于本地占位 provider",
                subtitle_text="这不是过去。",
                focus_roles=["林夏"],
            )
        ],
    )
    assembly_plan = AssemblyPlan(
        episode_title="真实规划图片占位视频测试-第一集",
        editing_style="快节奏",
        transitions=[],
        final_runtime_seconds=4,
        export_notes=["测试只跳过 Seedance"],
    )

    class FakeAgentTeamService:
        def __init__(self, workspace_root: Path):
            self.workspace_root = workspace_root
            calls["agent"] += 1

        def generate_story_plan(self, request, *, thread_id):  # noqa: ANN001
            return plan

        def generate_assembly_plan(self, plan, *, thread_id):  # noqa: ANN001
            return assembly_plan

        def close(self) -> None:
            return None

    class FakeImageProvider:
        def generate_image(self, *, prompt: str, aspect_ratio: str, output_path: Path) -> Path:
            from projects.ai_short_drama.backend.app.services.placeholder_media_service import PlaceholderMediaService

            calls["image"] += 1
            PlaceholderMediaService._write_placeholder_png(
                output_path,
                title="真实图片 provider 替身",
                subtitle=prompt,
                accent=(34, 112, 147),
            )
            return output_path

    def fail_seedance_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["seedance"] += 1
        raise AssertionError("use_placeholder_videos=True 时不应初始化 SeedanceVideoProvider")

    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.AgentTorchDramaTeamService",
        FakeAgentTeamService,
    )
    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.NanobananaImageProvider",
        FakeImageProvider,
    )
    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.SeedanceVideoProvider",
        fail_seedance_provider,
    )

    result = DramaPipelineService(tmp_path / "workspace").run(request)
    project_dir = Path(result.project_dir)

    assert calls["agent"] == 1
    assert calls["image"] == 3
    assert calls["seedance"] == 0
    assert (project_dir / "roles" / "images" / "role_01.png").is_file()
    assert (project_dir / "storyboard" / "images" / "shot_01.png").is_file()
    assert (project_dir / "storyboard" / "end_frames" / "shot_01_end.png").is_file()
    segment_video_paths = sorted((project_dir / "video" / "segments").glob("shot_01_seg_01.*"))
    shot_video_paths = sorted((project_dir / "video" / "shots").glob("shot_01.*"))
    assert len(segment_video_paths) == 1
    assert len(shot_video_paths) == 1
    assert segment_video_paths[0].suffix in {".avi", ".mp4"}
    assert shot_video_paths[0].suffix in {".avi", ".mp4"}

    manifest = json.loads((project_dir / "logs" / "manifest.json").read_text(encoding="utf-8"))
    stage_names = {stage["stage_name"] for stage in manifest["stage_records"]}
    assert "agent_planning" in stage_names
    assert "role_images" in stage_names
    assert "shot_generation" in stage_names
    assert "placeholder_video_generation" in stage_names
    assert "placeholder_planning" not in stage_names
