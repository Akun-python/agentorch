from __future__ import annotations

import base64
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    DramaProjectRequest,
    RoleCard,
    ShortDramaPlan,
    ShotPlan,
)
from projects.ai_short_drama.backend.app.providers.video_provider import SeedanceVideoProvider
from projects.ai_short_drama.backend.app.services.drama_pipeline_service import DramaPipelineService


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
                video_prompt="镜头跟随主角进入走廊，气氛压抑",
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
                video_prompt="从主角背后推进到墙上的血字，气氛骤紧",
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


def test_pipeline_uses_previous_tail_frame_for_next_shot(tmp_path: Path, monkeypatch) -> None:
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
        project_id="continuity-case",
    )
    plan = _build_plan()
    assembly_plan = _build_assembly_plan()
    storyboard_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
    )
    tail_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAusB8fRqp8QAAAAASUVORK5CYII="
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

        def create_video_task(self, **kwargs):  # noqa: ANN003
            self.create_calls.append(kwargs)
            return f"task-{len(self.create_calls)}"

        def wait_for_video_result(self, task_id: str) -> dict:
            return {
                "status": "succeeded",
                "content": {
                    "video_url": f"https://example.com/{task_id}.mp4",
                    "last_frame_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAusB8fRqp8QAAAAASUVORK5CYII=",
                },
            }

        @staticmethod
        def extract_video_url(video_result: dict) -> str | None:
            return video_result.get("content", {}).get("video_url")

        @staticmethod
        def extract_last_frame_url(video_result: dict) -> str | None:
            return video_result.get("content", {}).get("last_frame_url")

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
        lambda: fake_video_provider,
    )

    service = DramaPipelineService(tmp_path / "workspace")
    result = service.run(request)

    assert len(fake_video_provider.create_calls) == 2

    first_call = fake_video_provider.create_calls[0]
    second_call = fake_video_provider.create_calls[1]

    assert first_call["first_frame_local_path"].name == "shot_01.png"
    assert first_call["reference_image_local_paths"] == []
    assert first_call["return_last_frame"] is True

    assert second_call["first_frame_local_path"].name == "shot_01_tail.png"
    assert len(second_call["reference_image_local_paths"]) == 1
    assert second_call["reference_image_local_paths"][0].name == "shot_02.png"
    assert "延续上一镜头尾帧中的角色站位" in second_call["prompt"]

    tail_assets = [asset for asset in result.generated_assets if asset.asset_type == "shot_tail_frame"]
    assert len(tail_assets) == 2

    shot_stage = next(stage for stage in result.stage_records if stage.stage_name == "shot_generation")
    assert shot_stage.metadata["video_count"] == 2
    assert shot_stage.metadata["continuity_link_count"] == 1
    assert shot_stage.metadata["tail_frame_count"] == 2

    second_shot_asset = next(
        asset for asset in result.generated_assets if asset.asset_type == "shot_video" and asset.metadata.get("shot_no") == 2
    )
    assert second_shot_asset.metadata["continuity_first_frame"] == "previous_tail_frame"
    assert second_shot_asset.metadata["continuity_previous_tail_used"] is True
