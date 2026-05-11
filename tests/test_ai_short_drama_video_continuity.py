from __future__ import annotations

import base64
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    DramaProjectRequest,
    RoleCard,
    ShortDramaPlan,
    ShotSegmentPlanItem,
    ShotSegmentPlanSheet,
    ShotPlan,
    TransitionPlan,
)
from projects.ai_short_drama.backend.app.providers.video_provider import SeedanceVideoProvider
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.services.execution_design_service import ExecutionDesignService
from projects.ai_short_drama.backend.app.services.drama_pipeline_service import DramaPipelineService
from projects.ai_short_drama.backend.app.services.shot_generation_service import ShotGenerationService


def _build_plan() -> ShortDramaPlan:
    return ShortDramaPlan(
        project_title="连续性测试短剧",
        logline="测试尾帧衔接",
        visual_style="都市悬疑",
        episode_summary="两镜头连续测试",
        roles=[
            RoleCard(
                name="沈知",
                appearance="深色大衣",
                personality="克制警觉",
                relationship="主角",
                avatar_prompt="都市悬疑男主，深色大衣",
                voice_style="低沉克制",
            )
        ],
        shots=[
            ShotPlan(
                shot_no=1,
                title="镜头一",
                summary="主角推门进入走廊",
                duration_seconds=4,
                ratio="16:9",
                first_frame_prompt="昏暗走廊入口，主角推门而入",
                end_frame_prompt="主角站在走廊中段回头，手仍扶着门把手",
                video_prompt="镜头跟随主角进入走廊，气氛压抑",
                continuity_notes=["深色大衣和门把手位置保持稳定", "主光从走廊左侧延续"],
                subtitle_text="有人来过。",
                focus_roles=["沈知"],
            ),
            ShotPlan(
                shot_no=2,
                title="镜头二",
                summary="主角在尽头停住，发现墙上的血字",
                duration_seconds=5,
                ratio="16:9",
                first_frame_prompt="走廊尽头，墙面血字特写",
                end_frame_prompt="主角停在血字前，右手握着手机，视线盯住墙面",
                video_prompt="从主角背后推进到墙上的血字，气氛骤紧",
                continuity_notes=["深色大衣不变", "主角视线从走廊延续到墙面"],
                subtitle_text="不对劲。",
                focus_roles=["沈知"],
            ),
        ],
    )


def _build_assembly_plan() -> AssemblyPlan:
    return AssemblyPlan(
        episode_title="连续性测试短剧-第一集",
        editing_style="悬疑压迫",
        transitions=[],
        final_runtime_seconds=9.0,
        export_notes=["验证镜头连续性"],
    )


def test_video_provider_create_task_supports_reference_images_and_last_frame(tmp_path: Path) -> None:
    first_frame_path = tmp_path / "first.png"
    last_frame_path = tmp_path / "tail.png"
    reference_path = tmp_path / "reference.png"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
    )
    first_frame_path.write_bytes(png_bytes)
    last_frame_path.write_bytes(png_bytes)
    reference_path.write_bytes(png_bytes)

    provider = SeedanceVideoProvider.__new__(SeedanceVideoProvider)
    provider.api_key = "test-key"
    provider.url = "https://example.com/v1/responses"
    provider.model = "test-model"
    provider.query_model = "seedance-2-0-get"
    provider.disable_env_proxy = True
    provider.default_resolution = "720p"
    provider.default_ratio = "adaptive"
    provider.default_duration = 4
    provider.default_generate_audio = True
    provider.default_return_last_frame = False

    captured: dict = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"id": "task-123"}

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json, timeout):  # noqa: ANN001
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            captured["timeout"] = timeout
            return _FakeResponse()

    provider._make_session = lambda: _FakeSession()  # type: ignore[method-assign]

    task_id = provider.create_video_task(
        prompt="测试连续性提示词",
        first_frame_local_path=first_frame_path,
        last_frame_local_path=last_frame_path,
        reference_image_local_paths=[reference_path],
        ratio="16:9",
        duration_seconds=6,
        return_last_frame=True,
    )

    assert task_id == "task-123"
    payload = captured["payload"]
    assert payload["return_last_frame"] is True
    assert payload["ratio"] == "16:9"
    assert payload["duration"] == 6
    assert payload["input"][1]["role"] == "first_frame"
    assert payload["input"][2]["role"] == "last_frame"
    assert payload["input"][3]["role"] == "reference_image"
    assert payload["input"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_video_provider_extracts_last_frame_variants() -> None:
    provider = SeedanceVideoProvider.__new__(SeedanceVideoProvider)

    assert provider.extract_last_frame_url({"content": {"last_frame_url": "https://example.com/tail.png"}}) == "https://example.com/tail.png"
    assert provider.extract_last_frame_url({"content": {"last_frame": {"url": "https://example.com/tail2.png"}}}) == "https://example.com/tail2.png"
    assert provider.extract_last_frame_url({"meta_data": {"last_frame_image": "data:image/png;base64,AAAA"}}) == "data:image/png;base64,AAAA"


def test_video_provider_download_last_frame_supports_data_url(tmp_path: Path) -> None:
    provider = SeedanceVideoProvider.__new__(SeedanceVideoProvider)
    output_path = tmp_path / "tail.png"
    expected_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
    )

    result = provider.download_last_frame(
        last_frame_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII=",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.read_bytes() == expected_bytes


def test_execution_design_builds_structured_segment_and_audio_bridge() -> None:
    plan = _build_plan()
    assembly_plan = _build_assembly_plan()
    assembly_plan.transitions = [
        TransitionPlan(
            transition_no=1,
            from_shot_no=1,
            to_shot_no=2,
            transition_type="match_cut",
            duration_seconds=0.4,
            overlap_seconds=0.35,
            audio_bridge="门轴低频声延续到血字镜头",
            visual_prompt="沿着走廊暗线匹配剪切",
            summary="用走廊线条匹配剪切",
        )
    ]

    service = ExecutionDesignService()
    segment_plan = service.build_shot_segment_plan(plan, max_segment_seconds=4)
    cue_sheet = service.build_audio_cue_sheet(plan, assembly_plan)
    checklist = service.build_continuity_checklist(plan)

    assert segment_plan.segments
    assert segment_plan.segments[0].target_end_frame == plan.shots[0].end_frame_prompt
    assert any(cue.cue_type == "audio_bridge" for cue in cue_sheet.cues)
    assert any(cue.cue_type == "transition_audio_bridge" for cue in cue_sheet.cues)
    assert any(item.category == "end_frame" for item in checklist.items)
    assert any(item.category == "camera_axis" for item in checklist.items)


def test_segment_plan_never_expands_total_duration() -> None:
    plan = _build_plan()
    service = ExecutionDesignService()

    segment_plan = service.build_shot_segment_plan(plan, max_segment_seconds=4)

    durations_by_shot: dict[int, int] = {}
    for segment in segment_plan.segments:
        durations_by_shot[segment.shot_no] = durations_by_shot.get(segment.shot_no, 0) + segment.duration_seconds
        assert segment.duration_seconds >= 4

    assert durations_by_shot[1] == 4
    assert durations_by_shot[2] == 5


def test_shot_generation_service_uses_tail_frames_reference_images_and_retries(tmp_path: Path) -> None:
    request = DramaProjectRequest(
        project_name="连续性测试",
        premise="一名调查员在走廊追查真相",
        style="悬疑",
        episode_goal="验证连续性",
        role_count=1,
        shot_count=2,
        generate_role_images=False,
        generate_storyboard_images=True,
        generate_shot_videos=True,
        generate_transition_images=False,
        assemble_episode_video=False,
        render_shot_limit=2,
        max_continuity_retries=1,
        enable_multi_reference_images=True,
        project_id="continuity-case",
    )
    plan = _build_plan()
    storyboard_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
    )
    tail_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAusB8fRqp8QAAAAASUVORK5CYII="
    )

    class FakeImageProvider:
        def __init__(self) -> None:
            self.generated_paths: list[Path] = []

        def generate_image(self, *, prompt: str, aspect_ratio: str, output_path: Path) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(storyboard_png)
            self.generated_paths.append(output_path)
            return output_path

    class FakeVideoProvider:
        def __init__(self) -> None:
            self.create_calls: list[dict] = []
            self.download_last_frame_calls: list[dict] = []
            self.result_index = 0

        def create_video_task(self, **kwargs):  # noqa: ANN003
            self.create_calls.append(kwargs)
            return f"task-{len(self.create_calls)}"

        def wait_for_video_result(self, task_id: str) -> dict:
            self.result_index += 1
            return {
                "status": "succeeded",
                "content": {
                    "video_url": f"https://example.com/{task_id}.mp4",
                    "last_frame_url": (
                        ""
                        if self.result_index == 1
                        else "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAusB8fRqp8QAAAAASUVORK5CYII="
                    ),
                },
            }

        @staticmethod
        def extract_video_url(video_result: dict) -> str | None:
            return video_result.get("content", {}).get("video_url")

        @staticmethod
        def extract_last_frame_url(video_result: dict) -> str | None:
            return video_result.get("content", {}).get("last_frame_url") or None

        def download_video(self, *, video_url: str, output_path: Path) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return output_path

        def download_last_frame(self, *, last_frame_url: str, output_path: Path) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(tail_png)
            self.download_last_frame_calls.append({"url": last_frame_url, "path": output_path})
            return output_path

    fake_video_provider = FakeVideoProvider()
    repository = ProjectRepository(tmp_path / "workspace")
    project_dir = repository.ensure_project_layout("continuity-case")
    segment_plan = ShotSegmentPlanSheet(
        segments=[
            ShotSegmentPlanItem(
                shot_no=1,
                segment_no=1,
                segment_count=1,
                start_seconds=0.0,
                end_seconds=4.0,
                duration_seconds=4,
                prompt_focus="建立走廊空间",
                continuity_goal="角色和光线连续",
                target_end_frame=plan.shots[0].end_frame_prompt,
            ),
            ShotSegmentPlanItem(
                shot_no=2,
                segment_no=1,
                segment_count=1,
                start_seconds=0.0,
                end_seconds=5.0,
                duration_seconds=5,
                prompt_focus="推进到血字",
                continuity_goal="接上一镜尾帧",
                target_end_frame=plan.shots[1].end_frame_prompt,
            ),
        ]
    )

    service = ShotGenerationService(repository)
    result = service.generate(
        project_id="continuity-case",
        project_dir=project_dir,
        request=request,
        plan=plan,
        segment_plan=segment_plan,
        image_provider=FakeImageProvider(),
        video_provider=fake_video_provider,
        role_image_paths=[],
    )

    assert len(fake_video_provider.create_calls) == 3

    first_call = fake_video_provider.create_calls[0]
    first_retry_call = fake_video_provider.create_calls[1]
    second_call = fake_video_provider.create_calls[2]

    assert first_call["first_frame_local_path"].name == "shot_01.png"
    assert first_call["last_frame_local_path"].name == "shot_01_end.png"
    assert len(first_call["reference_image_local_paths"]) == 1
    assert first_call["return_last_frame"] is True
    assert "镜头结束尾帧必须贴近" in first_call["prompt"]
    assert "连续性重试要求" in first_retry_call["prompt"]

    assert second_call["first_frame_local_path"].name.startswith("shot_01_seg_01_tail")
    assert second_call["last_frame_local_path"].name == "shot_02_end.png"
    assert len(second_call["reference_image_local_paths"]) == 1
    assert second_call["reference_image_local_paths"][0].name == "shot_02.png"
    assert "首帧来自上一段或上一镜头尾帧" in second_call["prompt"]

    tail_assets = [asset for asset in result.generated_assets if asset.asset_type == "shot_tail_frame"]
    assert len(tail_assets) == 2

    assert result.stage_record.metadata["video_count"] == 2
    assert result.stage_record.metadata["continuity_link_count"] == 1
    assert result.stage_record.metadata["continuity_retry_count"] == 1
    assert (project_dir / "logs" / "continuity_report.json").is_file()


def test_shot_generation_blocks_multi_segment_merge_without_ffmpeg(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path / "workspace")
    service = ShotGenerationService(repository)
    service.ffmpeg_path = None

    segment_1 = tmp_path / "seg1.mp4"
    segment_2 = tmp_path / "seg2.mp4"
    output_path = tmp_path / "shot.mp4"
    segment_1.write_bytes(b"seg1")
    segment_2.write_bytes(b"seg2")

    result = service._build_shot_video_from_segments(
        segment_video_paths=[segment_1, segment_2],
        output_path=output_path,
    )

    assert result.output_path is None
    assert result.status == "blocked_ffmpeg_missing"
    assert result.fallback_manifest_path is not None
    assert result.fallback_manifest_path.is_file()
    assert not output_path.exists()


def test_pipeline_writes_segment_plan_and_continuity_report(tmp_path: Path, monkeypatch) -> None:
    request = DramaProjectRequest(
        project_name="连续性总流程测试",
        premise="调查员追查走廊血字",
        style="悬疑",
        episode_goal="验证总流程产物",
        role_count=1,
        shot_count=2,
        generate_role_images=False,
        generate_storyboard_images=True,
        generate_shot_videos=False,
        generate_transition_images=False,
        assemble_episode_video=False,
        render_shot_limit=2,
        project_id="pipeline-continuity-case",
    )
    plan = _build_plan()
    assembly_plan = _build_assembly_plan()
    storyboard_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
    )

    class FakeAgentTeamService:
        def __init__(self, workspace_root: Path):
            self.workspace_root = workspace_root

        def generate_story_plan(self, request, *, thread_id):  # noqa: ANN001
            return plan

        def generate_assembly_plan(self, plan, *, thread_id):  # noqa: ANN001
            return assembly_plan

        def close(self) -> None:
            return None

    class FakeImageProvider:
        def generate_image(self, *, prompt: str, aspect_ratio: str, output_path: Path) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(storyboard_png)
            return output_path

    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.AgentTorchDramaTeamService",
        FakeAgentTeamService,
    )
    monkeypatch.setattr(
        "projects.ai_short_drama.backend.app.services.drama_pipeline_service.NanobananaImageProvider",
        FakeImageProvider,
    )

    service = DramaPipelineService(tmp_path / "workspace")
    result = service.run(request)
    project_dir = Path(result.project_dir)

    assert (project_dir / "preproduction" / "shot_segment_plan.json").is_file()
    assert (project_dir / "logs" / "continuity_report.json").is_file()
    assert "shot_segment_plan.json" in (project_dir / "preproduction" / "browse_guide.txt").read_text(encoding="utf-8")
    assert any(asset.asset_type == "shot_segment_plan" for asset in result.generated_assets)
    assert any(asset.asset_type == "continuity_report" for asset in result.generated_assets)
