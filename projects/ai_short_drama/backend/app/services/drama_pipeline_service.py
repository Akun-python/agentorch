from __future__ import annotations

from datetime import datetime
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    DramaPipelineResult,
    DramaProjectRequest,
    GeneratedAsset,
    ProjectFileIndex,
    ProjectFileIndexItem,
    ProductionStageRecord,
)
from projects.ai_short_drama.backend.app.providers import NanobananaImageProvider, SeedanceVideoProvider
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.services.agent_team_service import AgentTorchDramaTeamService
from projects.ai_short_drama.backend.app.services.assembly_service import EpisodeAssemblyService
from projects.ai_short_drama.backend.app.services.editing_export_service import EditingExportService
from projects.ai_short_drama.backend.app.services.execution_design_service import ExecutionDesignService
from projects.ai_short_drama.backend.app.services.preproduction_service import (
    CharacterBibleService,
    DirectorNotebookService,
    QualityCheckService,
    SceneBeatService,
    StoryBibleService,
)
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

        story_bible = StoryBibleService().build(plan)
        character_bible = CharacterBibleService().build(plan)
        scene_beats = SceneBeatService().build(plan)
        director_notebook = DirectorNotebookService().build(plan)
        quality_report = QualityCheckService().build(plan, director_notebook)
        execution_design = ExecutionDesignService()
        shot_execution_sheet = execution_design.build_shot_execution_sheet(plan)
        subtitle_timeline = execution_design.build_subtitle_timeline(plan)
        audio_cue_sheet = execution_design.build_audio_cue_sheet(plan, assembly_plan)
        continuity_checklist = execution_design.build_continuity_checklist(plan)
        prop_inventory = execution_design.build_prop_inventory(plan)
        delivery_checklist = execution_design.build_delivery_checklist(plan, assembly_plan)

        story_bible_path = self.repository.preproduction_path(project_id, "story_bible.json")
        story_bible_path.write_text(story_bible.model_dump_json(indent=2), encoding="utf-8")
        character_bible_path = self.repository.preproduction_path(project_id, "character_bible.json")
        character_bible_path.write_text(character_bible.model_dump_json(indent=2), encoding="utf-8")
        scene_beats_path = self.repository.preproduction_path(project_id, "scene_beats.json")
        scene_beats_path.write_text(scene_beats.model_dump_json(indent=2), encoding="utf-8")
        director_notebook_path = self.repository.preproduction_path(project_id, "director_notebook.json")
        director_notebook_path.write_text(director_notebook.model_dump_json(indent=2), encoding="utf-8")
        quality_report_path = self.repository.preproduction_path(project_id, "quality_checks.json")
        quality_report_path.write_text(quality_report.model_dump_json(indent=2), encoding="utf-8")
        shot_execution_path = self.repository.preproduction_path(project_id, "shot_execution_sheet.json")
        shot_execution_path.write_text(shot_execution_sheet.model_dump_json(indent=2), encoding="utf-8")
        subtitle_timeline_path = self.repository.preproduction_path(project_id, "subtitle_timeline.json")
        subtitle_timeline_path.write_text(subtitle_timeline.model_dump_json(indent=2), encoding="utf-8")
        audio_cue_path = self.repository.preproduction_path(project_id, "audio_cue_sheet.json")
        audio_cue_path.write_text(audio_cue_sheet.model_dump_json(indent=2), encoding="utf-8")
        continuity_path = self.repository.preproduction_path(project_id, "continuity_checklist.json")
        continuity_path.write_text(continuity_checklist.model_dump_json(indent=2), encoding="utf-8")
        prop_inventory_path = self.repository.preproduction_path(project_id, "prop_inventory.json")
        prop_inventory_path.write_text(prop_inventory.model_dump_json(indent=2), encoding="utf-8")
        delivery_checklist_path = self.repository.preproduction_path(project_id, "delivery_checklist.json")
        delivery_checklist_path.write_text(delivery_checklist.model_dump_json(indent=2), encoding="utf-8")
        generated_assets.extend(
            [
                GeneratedAsset(
                    asset_type="story_bible",
                    relative_path=str(story_bible_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="character_bible",
                    relative_path=str(character_bible_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="scene_beats",
                    relative_path=str(scene_beats_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="director_notebook",
                    relative_path=str(director_notebook_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="quality_checks",
                    relative_path=str(quality_report_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="shot_execution_sheet",
                    relative_path=str(shot_execution_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="subtitle_timeline",
                    relative_path=str(subtitle_timeline_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="audio_cue_sheet",
                    relative_path=str(audio_cue_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="continuity_checklist",
                    relative_path=str(continuity_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="prop_inventory",
                    relative_path=str(prop_inventory_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
                GeneratedAsset(
                    asset_type="delivery_checklist",
                    relative_path=str(delivery_checklist_path.relative_to(project_dir)),
                    source_name=plan.project_title,
                    metadata={},
                ),
            ]
        )
        stage_records.append(
            ProductionStageRecord(
                stage_name="preproduction_detailing",
                status="completed",
                detail="已生成故事圣经、角色手册、场景节拍、导演手册、字幕时轴、音频 cue、连续性清单等前期细节文件",
            )
        )

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

        export_service = EditingExportService(self.repository)
        export_bundle, export_assets, export_stage = export_service.build_export_bundle(
            project_id=project_id,
            project_dir=project_dir,
            plan=plan,
            assembly_plan=assembly_plan,
            subtitle_timeline=subtitle_timeline,
            audio_cue_sheet=audio_cue_sheet,
            shot_video_paths=shot_video_paths,
        )
        stage_records.append(export_stage)
        generated_assets.extend(export_assets)

        project_index = ProjectFileIndex(
            project_id=project_id,
            items=[
                ProjectFileIndexItem(stage_name="request", file_path=str(request_path), description="本次项目请求参数"),
                ProjectFileIndexItem(stage_name="story_plan", file_path=str(plan_path), description="AgentTorch 团队输出的角色和镜头计划"),
                ProjectFileIndexItem(stage_name="assembly_plan", file_path=str(assembly_plan_path), description="AgentTorch 团队输出的成片装配方案"),
                ProjectFileIndexItem(stage_name="story_bible", file_path=str(story_bible_path), description="故事圣经"),
                ProjectFileIndexItem(stage_name="character_bible", file_path=str(character_bible_path), description="角色手册"),
                ProjectFileIndexItem(stage_name="scene_beats", file_path=str(scene_beats_path), description="场景节拍"),
                ProjectFileIndexItem(stage_name="director_notebook", file_path=str(director_notebook_path), description="导演镜头手册"),
                ProjectFileIndexItem(stage_name="quality_checks", file_path=str(quality_report_path), description="细节质检清单"),
                ProjectFileIndexItem(stage_name="shot_execution_sheet", file_path=str(shot_execution_path), description="镜头内动作节拍"),
                ProjectFileIndexItem(stage_name="subtitle_timeline", file_path=str(subtitle_timeline_path), description="字幕时间轴"),
                ProjectFileIndexItem(stage_name="audio_cue_sheet", file_path=str(audio_cue_path), description="声音与音乐 cue 清单"),
                ProjectFileIndexItem(stage_name="continuity_checklist", file_path=str(continuity_path), description="连续性检查清单"),
                ProjectFileIndexItem(stage_name="prop_inventory", file_path=str(prop_inventory_path), description="道具清单"),
                ProjectFileIndexItem(stage_name="delivery_checklist", file_path=str(delivery_checklist_path), description="交付前检查表"),
                ProjectFileIndexItem(
                    stage_name="editing_export_bundle",
                    file_path=str(self.repository.export_path(project_id, "editing_export_bundle.json")),
                    description="开放格式导出包总索引，包含 draft/final 字幕与时间线",
                ),
            ],
        )
        index_path = self.repository.preproduction_path(project_id, "project_index.json")
        index_path.write_text(project_index.model_dump_json(indent=2), encoding="utf-8")
        browse_guide_path = self.repository.preproduction_path(project_id, "browse_guide.txt")
        browse_guide_path.write_text(
            "\n".join(
                [
                    "AI 短剧项目浏览顺序",
                    "===================",
                    "",
                    "1. logs/request.json",
                    "   看本次输入目标、开关和生成范围。",
                    "",
                    "2. preproduction/story_bible.json",
                    "   看故事圣经：主题、风格关键词、禁忌和必须保留的戏剧瞬间。",
                    "",
                    "3. preproduction/character_bible.json",
                    "   看角色手册：角色欲望、伤口、表演方向、视觉锚点。",
                    "",
                    "4. preproduction/scene_beats.json",
                    "   看场景节拍：每场戏的目标、冲突、揭示和离场钩子。",
                    "",
                    "5. script/plan.json",
                    "   看角色卡和镜头计划，是后续图片和视频生成的直接输入。",
                    "",
                    "6. preproduction/director_notebook.json",
                    "   看导演手册：镜头意图、构图、机位、表演、道具、声音和连续性风险。",
                    "",
                    "7. preproduction/quality_checks.json",
                    "   看需要人工盯的细节问题，避免直接进入生成后才返工。",
                    "",
                    "8. preproduction/shot_execution_sheet.json",
                    "   看每个镜头内部的动作节拍、情绪节点和执行重点。",
                    "",
                    "9. preproduction/subtitle_timeline.json",
                    "   看字幕从哪一秒进、哪一秒出，以及强调方式。",
                    "",
                    "10. preproduction/audio_cue_sheet.json",
                    "    看环境声、强调音、转场音效如何铺。",
                    "",
                    "11. preproduction/continuity_checklist.json",
                    "    看服装、视线、灯光、道具这些连续性检查点。",
                    "",
                    "12. preproduction/prop_inventory.json",
                    "    看每个关键道具在哪些镜头出现，是否需要连续控制。",
                    "",
                    "13. preproduction/delivery_checklist.json",
                    "    看最终交付前需要勾掉的事项。",
                    "",
                    "14. script/assembly_plan.json",
                    "   看后期节奏、转场和成片思路。",
                    "",
                    "15. exports/episode_assembly.json",
                    "   看最终装配清单，以及是否具备自动拼接条件。",
                    "",
                    "16. exports/editing_export_bundle.json",
                    "    看开放格式导出包，里面有 draft/final 的 SRT、FCPXML 与导出说明。",
                    "",
                    "17. subtitles/captions_draft.srt 与 subtitles/captions_final.srt",
                    "    给剪映桌面/Web 直接导字幕。",
                    "",
                    "18. exports/draft/timeline_draft.fcpxml 与 exports/final/timeline_final.fcpxml",
                    "    给专业剪辑软件导入时间线；draft 可先审稿，final 仅在镜头齐全时生成。",
                    "",
                    "19. logs/manifest.json",
                    "    看所有产物和阶段状态总表。",
                    "",
                    "20. preproduction/project_index.json",
                    "    这是全文件索引，适合程序或前端直接消费。",
                ]
            ),
            encoding="utf-8",
        )
        generated_assets.append(
            GeneratedAsset(
                asset_type="project_index",
                relative_path=str(index_path.relative_to(project_dir)),
                source_name=plan.project_title,
                metadata={},
            )
        )
        generated_assets.append(
            GeneratedAsset(
                asset_type="browse_guide",
                relative_path=str(browse_guide_path.relative_to(project_dir)),
                source_name=plan.project_title,
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
