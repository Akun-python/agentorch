from __future__ import annotations

from datetime import datetime
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    DramaPipelineResult,
    DramaProjectRequest,
    GeneratedAsset,
    ProductionStageRecord,
)
from projects.ai_short_drama.backend.app.providers import NanobananaImageProvider, SeedanceVideoProvider
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.services.agent_team_service import AgentTorchDramaTeamService
from projects.ai_short_drama.backend.app.services.assembly_service import EpisodeAssemblyService
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
        stage_records: list[ProductionStageRecord] = []

        request_path = self.repository.write_json(project_id, "logs/request.json", request.model_dump())

        agent_team = AgentTorchDramaTeamService(workspace_root=self.project_root)
        try:
            plan = agent_team.generate_story_plan(request, thread_id=f"{project_id}-story-team")
            assembly_plan = agent_team.generate_assembly_plan(plan, thread_id=f"{project_id}-assembly-team")
        finally:
            agent_team.close()
        plan = self._normalize_plan(plan, request)
        assembly_plan = self._normalize_assembly_plan(assembly_plan, plan)
        stage_records.append(
            ProductionStageRecord(
                stage_name="agent_planning",
                status="completed",
                detail="已通过 AgentTorch 多智能体团队完成剧本规划与装配方案",
            )
        )

        plan_path = self.repository.write_json(project_id, "script/plan.json", plan.model_dump())
        assembly_plan_path = self.repository.write_json(project_id, "script/assembly_plan.json", assembly_plan.model_dump())

        image_provider = None
        video_provider = None
        shot_video_paths: list[Path] = []
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
            stage_records.append(
                ProductionStageRecord(
                    stage_name="role_images",
                    status="completed",
                    detail="已生成角色图",
                    metadata={"count": min(len(plan.roles), request.render_role_image_limit)},
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
                    shot_video_paths.append(shot_video_path)
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_video",
                            relative_path=str(shot_video_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={"shot_no": shot.shot_no, "task_id": task_id},
                        )
                    )
            stage_records.append(
                ProductionStageRecord(
                    stage_name="shot_generation",
                    status="completed",
                    detail="已生成分镜图与镜头视频",
                    metadata={"video_count": len(shot_video_paths)},
                )
            )

        if request.generate_transition_images and image_provider is not None:
            for transition in assembly_plan.transitions[: request.render_transition_limit]:
                if not transition.visual_prompt:
                    continue
                transition_path = self.repository.transition_image_path(project_id, transition.transition_no)
                image_provider.generate_image(
                    prompt=transition.visual_prompt,
                    aspect_ratio=request.image_aspect_ratio,
                    output_path=transition_path,
                )
                generated_assets.append(
                    GeneratedAsset(
                        asset_type="transition_image",
                        relative_path=str(transition_path.relative_to(project_dir)),
                        source_name=f"transition_{transition.transition_no:02d}",
                        metadata={
                            "transition_no": transition.transition_no,
                            "from_shot_no": transition.from_shot_no,
                            "to_shot_no": transition.to_shot_no,
                        },
                    )
                )
            stage_records.append(
                ProductionStageRecord(
                    stage_name="transition_design",
                    status="completed",
                    detail="已生成转场画面素材",
                    metadata={"count": min(len(assembly_plan.transitions), request.render_transition_limit)},
                )
            )

        if request.assemble_episode_video:
            assembly_service = EpisodeAssemblyService()
            episode_package_path, assembly_stage, transition_cards = assembly_service.build_episode_package(
                project_dir=project_dir,
                plan=plan,
                assembly_plan=assembly_plan,
                shot_video_paths=shot_video_paths,
            )
            stage_records.append(assembly_stage)
            generated_assets.append(
                GeneratedAsset(
                    asset_type="episode_package",
                    relative_path=str(episode_package_path.relative_to(project_dir)),
                    source_name=assembly_plan.episode_title,
                    metadata={"editing_style": assembly_plan.editing_style},
                )
            )
            for card_path in transition_cards:
                generated_assets.append(
                    GeneratedAsset(
                        asset_type="transition_card",
                        relative_path=str(card_path.relative_to(project_dir)),
                        source_name=card_path.stem,
                        metadata={},
                    )
                )

        manifest = DramaPipelineResult(
            project_id=project_id,
            project_dir=str(project_dir),
            request_path=str(request_path),
            plan_path=str(plan_path),
            assembly_plan_path=str(assembly_plan_path),
            manifest_path=str(project_dir / "logs" / "manifest.json"),
            generated_assets=generated_assets,
            stage_records=stage_records,
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

    @staticmethod
    def _normalize_assembly_plan(assembly_plan: AssemblyPlan, plan) -> AssemblyPlan:
        shot_map = {shot.shot_no for shot in plan.shots}
        transitions = [
            transition
            for transition in assembly_plan.transitions
            if transition.from_shot_no in shot_map and transition.to_shot_no in shot_map
        ]
        total_runtime = float(sum(shot.duration_seconds for shot in plan.shots))
        return assembly_plan.model_copy(
            update={
                "transitions": transitions,
                "final_runtime_seconds": max(total_runtime, assembly_plan.final_runtime_seconds),
            }
        )
