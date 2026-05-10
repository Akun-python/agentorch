from __future__ import annotations

from datetime import datetime
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    DramaPipelineResult,
    DramaProjectRequest,
    GeneratedAsset,
)
from projects.ai_short_drama.backend.app.providers import (
    AgentTorchStoryPlanner,
    NanobananaImageProvider,
    SeedanceVideoProvider,
)
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.utils.env_loader import load_project_env


class DramaPipelineService:
    """编排短剧 LLM -> 图片 -> 视频的最小闭环。"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        load_project_env(self.project_root)
        self.repository = ProjectRepository(self.project_root)

    def run(self, request: DramaProjectRequest) -> DramaPipelineResult:
        project_id = request.project_id or self._build_project_id(request.project_name)
        project_dir = self.repository.ensure_project_layout(project_id)
        generated_assets: list[GeneratedAsset] = []

        request_path = self.repository.write_json(project_id, "logs/request.json", request.model_dump())

        planner = AgentTorchStoryPlanner(workspace_root=self.project_root)
        try:
            plan = planner.generate_plan(request, thread_id=f"{project_id}-plan")
        finally:
            planner.close()
        plan = self._normalize_plan(plan, request)

        plan_path = self.repository.write_json(project_id, "script/plan.json", plan.model_dump())

        image_provider = None
        video_provider = None
        if request.generate_role_images or request.generate_storyboard_images or request.generate_shot_videos:
            image_provider = NanobananaImageProvider()
        if request.generate_shot_videos:
            video_provider = SeedanceVideoProvider()

        if request.generate_role_images and image_provider is not None:
            for index, role in enumerate(plan.roles[: request.render_role_image_limit], start=1):
                output_path = self.repository.role_image_path(project_id, index)
                image_provider.generate_image(
                    prompt=role.avatar_prompt,
                    aspect_ratio=request.image_aspect_ratio,
                    output_path=output_path,
                )
                generated_assets.append(
                    GeneratedAsset(
                        asset_type="role_image",
                        relative_path=str(output_path.relative_to(project_dir)),
                        source_name=role.name,
                        metadata={"index": index},
                    )
                )

        if (request.generate_storyboard_images or request.generate_shot_videos) and image_provider is not None:
            for shot in plan.shots[: request.render_shot_limit]:
                shot_image_path = self.repository.shot_image_path(project_id, shot.shot_no)
                image_provider.generate_image(
                    prompt=shot.first_frame_prompt,
                    aspect_ratio=shot.ratio or request.image_aspect_ratio,
                    output_path=shot_image_path,
                )
                generated_assets.append(
                    GeneratedAsset(
                        asset_type="storyboard_image",
                        relative_path=str(shot_image_path.relative_to(project_dir)),
                        source_name=shot.title,
                        metadata={"shot_no": shot.shot_no},
                    )
                )

                if request.generate_shot_videos and video_provider is not None:
                    task_id = video_provider.create_video_task(
                        prompt=shot.video_prompt,
                        first_frame_local_path=shot_image_path,
                        ratio=shot.ratio,
                        duration_seconds=shot.duration_seconds,
                    )
                    video_result = video_provider.wait_for_video_result(task_id)
                    video_url = video_result.get("content", {}).get("video_url")
                    if not video_url:
                        raise RuntimeError(f"镜头 {shot.shot_no} 未返回 video_url")

                    shot_video_path = self.repository.shot_video_path(project_id, shot.shot_no)
                    video_provider.download_video(video_url=video_url, output_path=shot_video_path)
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_video",
                            relative_path=str(shot_video_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={"shot_no": shot.shot_no, "task_id": task_id},
                        )
                    )

        manifest = DramaPipelineResult(
            project_id=project_id,
            project_dir=str(project_dir),
            request_path=str(request_path),
            plan_path=str(plan_path),
            manifest_path=str(project_dir / "logs" / "manifest.json"),
            generated_assets=generated_assets,
        )
        manifest_path = self.repository.write_json(project_id, "logs/manifest.json", manifest.model_dump())
        return manifest

    def _build_project_id(self, project_name: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = self.repository.slugify_project_id(project_name)
        return f"{slug}_{timestamp}"

    @staticmethod
    def _normalize_plan(plan, request: DramaProjectRequest):
        if len(plan.roles) < request.role_count:
            raise ValueError(f"角色数量不足，期望 {request.role_count}，实际 {len(plan.roles)}")
        if len(plan.shots) < request.shot_count:
            raise ValueError(f"镜头数量不足，期望 {request.shot_count}，实际 {len(plan.shots)}")

        return plan.model_copy(
            update={
                "roles": plan.roles[: request.role_count],
                "shots": plan.shots[: request.shot_count],
            }
        )
