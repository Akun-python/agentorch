from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    ContinuityCheckReport,
    ContinuityCheckResult,
    DramaProjectRequest,
    GeneratedAsset,
    ProductionStageRecord,
    ShortDramaPlan,
    ShotPlan,
    ShotSegmentPlanItem,
    ShotSegmentPlanSheet,
)
from projects.ai_short_drama.backend.app.providers import NanobananaImageProvider, SeedanceVideoProvider
from projects.ai_short_drama.backend.app.repositories import ProjectRepository


@dataclass(slots=True)
class ShotGenerationResult:
    shot_video_paths: list[Path]
    generated_assets: list[GeneratedAsset]
    stage_record: ProductionStageRecord
    continuity_report: ContinuityCheckReport


@dataclass(slots=True)
class ShotVideoBuildResult:
    output_path: Path | None
    status: str
    fallback_manifest_path: Path | None = None


class ContinuityPromptBuilder:
    """把结构化连续性字段压成视频模型能执行的提示词。"""

    def build_segment_prompt(
        self,
        *,
        shot: ShotPlan,
        segment: ShotSegmentPlanItem,
        attempt_no: int,
        previous_tail_used: bool,
        retry_suffix: str = "",
    ) -> str:
        lines = [
            shot.video_prompt,
            f"本段重点：{segment.prompt_focus}",
            f"本段结束目标：{segment.target_end_frame}",
            f"镜头结束尾帧必须贴近：{shot.end_frame_prompt}",
            f"轴线：{shot.camera_axis.axis_description}；画面方向：{shot.camera_axis.screen_direction}；机位：{shot.camera_axis.camera_position}",
            f"灯光：主光={shot.lighting_state.key_light_direction}；色温={shot.lighting_state.color_temperature}；亮度={shot.lighting_state.brightness_level}",
        ]
        if shot.continuity_notes:
            lines.append("连续性要求：" + "；".join(shot.continuity_notes))
        if shot.character_state:
            character_lines = [
                (
                    f"{item.name}：站位={item.blocking}，姿态={item.pose}，表情={item.expression}，"
                    f"视线={item.eyeline}，服装={item.wardrobe_state}"
                )
                for item in shot.character_state
            ]
            lines.append("人物状态：" + "；".join(character_lines))
        if shot.prop_state:
            prop_lines = [
                f"{item.prop_name}：位置={item.placement}，朝向={item.orientation}，手位={item.hand_usage}"
                for item in shot.prop_state
            ]
            lines.append("道具状态：" + "；".join(prop_lines))
        if previous_tail_used:
            lines.append("首帧来自上一段或上一镜头尾帧，必须延续其中人物站位、手势、视线、道具和光线，不要突变。")
        if attempt_no > 1:
            lines.append(f"这是第 {attempt_no} 次重试，请优先修正连续性问题。")
        if retry_suffix:
            lines.append(retry_suffix)
        return " ".join(line for line in lines if line).strip()


class ContinuityQualityService:
    """轻量连续性质检；能用 PIL 时做图像差异，不能用时退化为规则检查。"""

    def check(
        self,
        *,
        shot: ShotPlan,
        segment: ShotSegmentPlanItem,
        attempt_no: int,
        previous_tail_frame_path: Path | None,
        current_tail_frame_path: Path | None,
        enable_visual_metrics: bool,
    ) -> ContinuityCheckResult:
        issues: list[str] = []
        metrics: dict = {}

        if current_tail_frame_path is None or not current_tail_frame_path.is_file():
            issues.append("未拿到当前段尾帧，无法继续稳态接续")
        if not shot.end_frame_prompt:
            issues.append("缺少 end_frame_prompt，尾帧目标不明确")
        if not shot.continuity_notes:
            issues.append("缺少 continuity_notes，跨镜头连续性约束不足")
        if not shot.camera_axis.axis_description:
            issues.append("缺少 camera_axis，存在跳轴风险")
        if not shot.lighting_state.key_light_direction:
            issues.append("缺少 lighting_state，灯光连续性不可控")
        if previous_tail_frame_path is not None and not previous_tail_frame_path.is_file():
            issues.append("上一段尾帧文件不存在，当前段无法承接真实首帧")

        if enable_visual_metrics and previous_tail_frame_path and current_tail_frame_path:
            metrics.update(self._compare_images(previous_tail_frame_path, current_tail_frame_path))
            mean_delta = metrics.get("mean_rgb_delta")
            if isinstance(mean_delta, (int, float)) and mean_delta > 95:
                issues.append("首尾帧平均颜色差异过大，可能存在灯光或场景突变")

        score = max(0.0, 100.0 - len(issues) * 22.0)
        retry_prompt_suffix = ""
        if issues:
            retry_prompt_suffix = " 连续性重试要求：" + "；".join(issues) + "。请保持人物、道具、视线、光线和镜头轴线稳定。"
        return ContinuityCheckResult(
            shot_no=shot.shot_no,
            segment_no=segment.segment_no,
            attempt_no=attempt_no,
            passed=not issues,
            score=score,
            issues=issues,
            retry_prompt_suffix=retry_prompt_suffix,
            metrics=metrics,
        )

    @staticmethod
    def _compare_images(previous_path: Path, current_path: Path) -> dict:
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            return {"visual_metrics": "PIL unavailable"}

        try:
            with Image.open(previous_path) as previous_image, Image.open(current_path) as current_image:
                previous_rgb = previous_image.convert("RGB").resize((32, 32))
                current_rgb = current_image.convert("RGB").resize((32, 32))
                diff = ImageChops.difference(previous_rgb, current_rgb)
                stat = ImageStat.Stat(diff)
                mean_delta = round(sum(stat.mean) / len(stat.mean), 3)
                return {
                    "mean_rgb_delta": mean_delta,
                    "previous_frame": str(previous_path),
                    "current_frame": str(current_path),
                }
        except OSError as exc:
            return {
                "visual_metrics": "image_read_failed",
                "visual_metrics_error": str(exc),
                "previous_frame": str(previous_path),
                "current_frame": str(current_path),
            }


class ShotGenerationService:
    """负责分镜图、短段视频、尾帧连续性和质检重试。"""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.prompt_builder = ContinuityPromptBuilder()
        self.quality_service = ContinuityQualityService()

    def generate(
        self,
        *,
        project_id: str,
        project_dir: Path,
        request: DramaProjectRequest,
        plan: ShortDramaPlan,
        segment_plan: ShotSegmentPlanSheet,
        image_provider: NanobananaImageProvider,
        video_provider: SeedanceVideoProvider | None,
        role_image_paths: list[Path],
    ) -> ShotGenerationResult:
        generated_assets: list[GeneratedAsset] = []
        shot_video_paths: list[Path] = []
        continuity_checks: list[ContinuityCheckResult] = []
        previous_tail_frame_path: Path | None = None
        continuity_link_count = 0
        retry_count = 0
        segment_count = 0

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

            end_frame_path = self.repository.shot_end_frame_image_path(project_id, shot.shot_no)
            image_provider.generate_image(
                prompt=shot.end_frame_prompt,
                aspect_ratio=shot.ratio or request.image_aspect_ratio,
                output_path=end_frame_path,
            )
            generated_assets.append(
                GeneratedAsset(
                    asset_type="target_end_frame",
                    relative_path=str(end_frame_path.relative_to(project_dir)),
                    source_name=shot.title,
                    metadata={"shot_no": shot.shot_no},
                )
            )

            if request.generate_shot_videos and video_provider is not None:
                shot_segments = [segment for segment in segment_plan.segments if segment.shot_no == shot.shot_no]
                segment_video_paths: list[Path] = []
                for segment in shot_segments:
                    segment_count += 1
                    final_segment_path, final_tail_path, checks, used_previous_tail = self._generate_segment_with_retry(
                        project_id=project_id,
                        request=request,
                        shot=shot,
                        segment=segment,
                        video_provider=video_provider,
                        first_frame_path=previous_tail_frame_path or shot_image_path,
                        target_end_frame_path=end_frame_path,
                        reference_image_paths=self._build_reference_images(
                            request=request,
                            shot_image_path=shot_image_path,
                            role_image_paths=role_image_paths,
                        ),
                        previous_tail_frame_path=previous_tail_frame_path,
                    )
                    continuity_checks.extend(checks)
                    if len(checks) > 1:
                        retry_count += len(checks) - 1
                    if final_tail_path:
                        previous_tail_frame_path = final_tail_path
                    else:
                        previous_tail_frame_path = None
                    if used_previous_tail and final_tail_path:
                        continuity_link_count += 1
                    segment_video_paths.append(final_segment_path)
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_segment_video",
                            relative_path=str(final_segment_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={
                                "shot_no": shot.shot_no,
                                "segment_no": segment.segment_no,
                                "segment_count": segment.segment_count,
                            },
                        )
                    )
                    if final_tail_path:
                        generated_assets.append(
                            GeneratedAsset(
                                asset_type="shot_segment_tail_frame",
                                relative_path=str(final_tail_path.relative_to(project_dir)),
                                source_name=shot.title,
                                metadata={"shot_no": shot.shot_no, "segment_no": segment.segment_no},
                            )
                        )

                shot_video_path = self.repository.shot_video_path(project_id, shot.shot_no)
                shot_build = self._build_shot_video_from_segments(
                    segment_video_paths=segment_video_paths,
                    output_path=shot_video_path,
                )
                if shot_build.output_path is not None:
                    shot_video_paths.append(shot_build.output_path)
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_video",
                            relative_path=str(shot_build.output_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={
                                "shot_no": shot.shot_no,
                                "segment_count": len(segment_video_paths),
                                "build_status": shot_build.status,
                                "continuity_tail_frame_generated": previous_tail_frame_path is not None,
                                "continuity_first_frame": "previous_tail_frame" if shot.shot_no > 1 else "storyboard_image",
                            },
                        )
                    )
                if shot_build.fallback_manifest_path is not None:
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_segment_manifest",
                            relative_path=str(shot_build.fallback_manifest_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={"shot_no": shot.shot_no, "build_status": shot_build.status},
                        )
                    )
                if previous_tail_frame_path:
                    shot_tail_frame_path = self.repository.shot_tail_frame_path(project_id, shot.shot_no)
                    shot_tail_frame_path.write_bytes(previous_tail_frame_path.read_bytes())
                    generated_assets.append(
                        GeneratedAsset(
                            asset_type="shot_tail_frame",
                            relative_path=str(shot_tail_frame_path.relative_to(project_dir)),
                            source_name=shot.title,
                            metadata={"shot_no": shot.shot_no},
                        )
                    )

        continuity_report = ContinuityCheckReport(checks=continuity_checks)
        report_path = self.repository.write_json(project_id, "logs/continuity_report.json", continuity_report.model_dump())
        generated_assets.append(
            GeneratedAsset(
                asset_type="continuity_report",
                relative_path=str(report_path.relative_to(project_dir)),
                source_name=plan.project_title,
                metadata={"check_count": len(continuity_checks), "retry_count": retry_count},
            )
        )
        stage_record = ProductionStageRecord(
            stage_name="shot_generation",
            status="completed" if shot_video_paths or not request.generate_shot_videos else "skipped",
            detail="已生成分镜图、目标尾帧、短段视频、连续性尾帧与质检报告",
            metadata={
                "video_count": len(shot_video_paths),
                "segment_count": segment_count,
                "continuity_link_count": continuity_link_count,
                "continuity_retry_count": retry_count,
                "tail_frame_count": len([asset for asset in generated_assets if asset.asset_type in {"shot_tail_frame", "shot_segment_tail_frame"}]),
                "continuity_report": str(report_path),
            },
        )
        return ShotGenerationResult(
            shot_video_paths=shot_video_paths,
            generated_assets=generated_assets,
            stage_record=stage_record,
            continuity_report=continuity_report,
        )

    def _generate_segment_with_retry(
        self,
        *,
        project_id: str,
        request: DramaProjectRequest,
        shot: ShotPlan,
        segment: ShotSegmentPlanItem,
        video_provider: SeedanceVideoProvider,
        first_frame_path: Path,
        target_end_frame_path: Path,
        reference_image_paths: list[Path],
        previous_tail_frame_path: Path | None,
    ) -> tuple[Path, Path | None, list[ContinuityCheckResult], bool]:
        checks: list[ContinuityCheckResult] = []
        retry_suffix = ""
        max_attempts = 1 + (request.max_continuity_retries if request.enable_continuity_qc else 0)
        used_previous_tail = first_frame_path == previous_tail_frame_path and previous_tail_frame_path is not None
        final_video_path = self.repository.shot_segment_video_path(project_id, shot.shot_no, segment.segment_no)
        final_tail_path: Path | None = None

        for attempt_no in range(1, max_attempts + 1):
            prompt = self.prompt_builder.build_segment_prompt(
                shot=shot,
                segment=segment,
                attempt_no=attempt_no,
                previous_tail_used=used_previous_tail,
                retry_suffix=retry_suffix,
            )
            task_id = video_provider.create_video_task(
                prompt=prompt,
                first_frame_local_path=first_frame_path,
                last_frame_local_path=target_end_frame_path,
                reference_image_local_paths=reference_image_paths,
                ratio=shot.ratio,
                duration_seconds=segment.duration_seconds,
                return_last_frame=True,
            )
            video_result = video_provider.wait_for_video_result(task_id)
            video_url = video_provider.extract_video_url(video_result)
            if not video_url:
                raise RuntimeError(f"镜头 {shot.shot_no} 分段 {segment.segment_no} 未返回 video_url")

            candidate_video_path = self._attempt_video_path(final_video_path, attempt_no)
            video_provider.download_video(video_url=video_url, output_path=candidate_video_path)
            tail_frame_url = video_provider.extract_last_frame_url(video_result)
            candidate_tail_path = None
            if tail_frame_url:
                candidate_tail_path = self.repository.shot_segment_tail_frame_path(project_id, shot.shot_no, segment.segment_no)
                if attempt_no > 1:
                    candidate_tail_path = candidate_tail_path.with_name(
                        f"{candidate_tail_path.stem}_attempt_{attempt_no:02d}{candidate_tail_path.suffix}"
                    )
                video_provider.download_last_frame(last_frame_url=tail_frame_url, output_path=candidate_tail_path)

            check = self.quality_service.check(
                shot=shot,
                segment=segment,
                attempt_no=attempt_no,
                previous_tail_frame_path=previous_tail_frame_path,
                current_tail_frame_path=candidate_tail_path,
                enable_visual_metrics=request.enable_continuity_qc,
            )
            checks.append(check)
            if check.passed or attempt_no == max_attempts:
                final_video_path.parent.mkdir(parents=True, exist_ok=True)
                if candidate_video_path != final_video_path:
                    shutil.copyfile(candidate_video_path, final_video_path)
                final_tail_path = candidate_tail_path
                break
            retry_suffix = check.retry_prompt_suffix

        return final_video_path, final_tail_path, checks, used_previous_tail

    @staticmethod
    def _build_reference_images(
        *,
        request: DramaProjectRequest,
        shot_image_path: Path,
        role_image_paths: list[Path],
    ) -> list[Path]:
        if not request.enable_multi_reference_images:
            return []
        references = [shot_image_path]
        references.extend(path for path in role_image_paths if path.is_file())
        return references[:4]

    @staticmethod
    def _attempt_video_path(final_video_path: Path, attempt_no: int) -> Path:
        if attempt_no == 1:
            return final_video_path
        return final_video_path.with_name(f"{final_video_path.stem}_attempt_{attempt_no:02d}{final_video_path.suffix}")

    def _build_shot_video_from_segments(self, *, segment_video_paths: list[Path], output_path: Path) -> ShotVideoBuildResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not segment_video_paths:
            return ShotVideoBuildResult(output_path=None, status="missing_segments")
        if len(segment_video_paths) == 1:
            shutil.copyfile(segment_video_paths[0], output_path)
            return ShotVideoBuildResult(output_path=output_path, status="single_segment_copy")
        if not self.ffmpeg_path:
            package_path = output_path.with_suffix(".segments.json")
            package_path.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "ffmpeg_missing",
                        "segments": [str(path) for path in segment_video_paths],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return ShotVideoBuildResult(output_path=None, status="blocked_ffmpeg_missing", fallback_manifest_path=package_path)

        concat_list = output_path.with_name(f"{output_path.stem}_segments.txt")
        concat_lines = [f"file '{path.as_posix()}'" for path in segment_video_paths]
        concat_list.write_text("\n".join(concat_lines), encoding="utf-8")
        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return ShotVideoBuildResult(output_path=output_path, status="ffmpeg_concat")
        except subprocess.CalledProcessError:
            package_path = output_path.with_suffix(".segments.json")
            package_path.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "ffmpeg_concat_failed",
                        "segments": [str(path) for path in segment_video_paths],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return ShotVideoBuildResult(output_path=None, status="blocked_ffmpeg_concat_failed", fallback_manifest_path=package_path)
