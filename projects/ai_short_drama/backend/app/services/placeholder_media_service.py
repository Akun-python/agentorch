from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    ContinuityCheckReport,
    ContinuityCheckResult,
    DramaProjectRequest,
    GeneratedAsset,
    ProductionStageRecord,
    ShortDramaPlan,
    ShotSegmentPlanSheet,
)
from projects.ai_short_drama.backend.app.repositories import ProjectRepository
from projects.ai_short_drama.backend.app.services.placeholder_video_writer import write_placeholder_avi
from projects.ai_short_drama.backend.app.services.shot_generation_service import ShotGenerationResult


@dataclass(slots=True)
class PlaceholderShotMediaResult:
    shot_video_paths: list[Path]
    generated_assets: list[GeneratedAsset]
    continuity_report: ContinuityCheckReport
    ffmpeg_available: bool
    playable_video_count: int
    placeholder_file_count: int


class PlaceholderMediaService:
    """生成本地占位图片、视频和连续性报告。"""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self.ffmpeg_path = shutil.which("ffmpeg")

    def generate_role_images(
        self,
        *,
        project_id: str,
        project_dir: Path,
        plan: ShortDramaPlan,
        request: DramaProjectRequest,
    ) -> tuple[list[Path], list[GeneratedAsset]]:
        role_image_paths: list[Path] = []
        assets: list[GeneratedAsset] = []
        for index, role in enumerate(plan.roles[: request.render_role_image_limit], start=1):
            output_path = self.repository.role_image_path(project_id, index)
            self._write_placeholder_png(
                output_path,
                title=role.name,
                subtitle=role.appearance,
                accent=self._accent_for_index(index),
            )
            role_image_paths.append(output_path)
            assets.append(
                GeneratedAsset(
                    asset_type="placeholder_role_image",
                    relative_path=str(output_path.relative_to(project_dir)),
                    source_name=role.name,
                    metadata={"index": index, "placeholder_media": True},
                )
            )
        return role_image_paths, assets

    def generate_shot_media(
        self,
        *,
        project_id: str,
        project_dir: Path,
        request: DramaProjectRequest,
        plan: ShortDramaPlan,
        segment_plan: ShotSegmentPlanSheet,
    ) -> PlaceholderShotMediaResult:
        shot_video_paths: list[Path] = []
        assets: list[GeneratedAsset] = []
        continuity_checks: list[ContinuityCheckResult] = []
        playable_video_count = 0
        placeholder_file_count = 0
        previous_tail_frame_path: Path | None = None

        for shot in plan.shots[: request.render_shot_limit]:
            shot_image_path = self.repository.shot_image_path(project_id, shot.shot_no)
            self._write_placeholder_png(
                shot_image_path,
                title=f"镜头{shot.shot_no:02d} 首帧",
                subtitle=shot.title,
                accent=self._accent_for_index(shot.shot_no),
            )
            assets.append(self._asset("placeholder_storyboard_image", shot_image_path, project_dir, shot.title, {"shot_no": shot.shot_no}))

            end_frame_path = self.repository.shot_end_frame_image_path(project_id, shot.shot_no)
            self._write_placeholder_png(
                end_frame_path,
                title=f"镜头{shot.shot_no:02d} 目标尾帧",
                subtitle=shot.end_frame_prompt[:42],
                accent=self._accent_for_index(shot.shot_no + 10),
            )
            assets.append(self._asset("placeholder_target_end_frame", end_frame_path, project_dir, shot.title, {"shot_no": shot.shot_no}))

            if not request.generate_shot_videos:
                continue

            segment_paths: list[Path] = []
            shot_segments = [segment for segment in segment_plan.segments if segment.shot_no == shot.shot_no]
            for segment in shot_segments:
                segment_path = self._placeholder_segment_video_path(project_id, shot.shot_no, segment.segment_no)
                tail_frame_path = self.repository.shot_segment_tail_frame_path(project_id, shot.shot_no, segment.segment_no)
                playable = self._write_placeholder_video(
                    segment_path,
                    duration_seconds=segment.duration_seconds,
                    shot_no=shot.shot_no,
                    segment_no=segment.segment_no,
                )
                playable_video_count += 1 if playable else 0
                placeholder_file_count += 0 if playable else 1
                self._write_placeholder_png(
                    tail_frame_path,
                    title=f"镜头{shot.shot_no:02d} 段{segment.segment_no:02d} 尾帧",
                    subtitle=segment.target_end_frame[:42],
                    accent=self._accent_for_index(shot.shot_no + segment.segment_no + 20),
                )
                segment_paths.append(segment_path)
                assets.append(
                    self._asset(
                        "placeholder_shot_segment_video",
                        segment_path,
                        project_dir,
                        shot.title,
                        {
                            "shot_no": shot.shot_no,
                            "segment_no": segment.segment_no,
                            "segment_count": segment.segment_count,
                            "duration_seconds": segment.duration_seconds,
                            "playable": playable,
                        },
                    )
                )
                assets.append(
                    self._asset(
                        "placeholder_shot_segment_tail_frame",
                        tail_frame_path,
                        project_dir,
                        shot.title,
                        {"shot_no": shot.shot_no, "segment_no": segment.segment_no},
                    )
                )
                continuity_checks.append(
                    self._build_continuity_check(
                        shot_no=shot.shot_no,
                        segment_no=segment.segment_no,
                        project_dir=project_dir,
                        first_frame_path=previous_tail_frame_path or shot_image_path,
                        end_frame_path=end_frame_path,
                        tail_frame_path=tail_frame_path,
                        playable=playable,
                    )
                )
                previous_tail_frame_path = tail_frame_path

            shot_video_path = self._placeholder_shot_video_path(project_id, shot.shot_no)
            shot_playable = self._build_placeholder_shot_video(segment_paths=segment_paths, output_path=shot_video_path)
            if shot_video_path.is_file():
                shot_video_paths.append(shot_video_path)
                playable_video_count += 1 if shot_playable else 0
                placeholder_file_count += 0 if shot_playable else 1
                assets.append(
                    self._asset(
                        "placeholder_shot_video",
                        shot_video_path,
                        project_dir,
                        shot.title,
                        {"shot_no": shot.shot_no, "segment_count": len(segment_paths), "playable": shot_playable},
                    )
                )
            if previous_tail_frame_path and previous_tail_frame_path.is_file():
                shot_tail_path = self.repository.shot_tail_frame_path(project_id, shot.shot_no)
                shutil.copyfile(previous_tail_frame_path, shot_tail_path)
                assets.append(self._asset("placeholder_shot_tail_frame", shot_tail_path, project_dir, shot.title, {"shot_no": shot.shot_no}))

        continuity_report = ContinuityCheckReport(checks=continuity_checks)
        report_path = self.repository.write_json(project_id, "logs/continuity_report.json", continuity_report.model_dump())
        assets.append(
            self._asset(
                "placeholder_continuity_report",
                report_path,
                project_dir,
                plan.project_title,
                {"check_count": len(continuity_checks)},
            )
        )
        media_manifest_path = self.repository.write_json(
            project_id,
            "logs/placeholder_media_manifest.json",
            {
                "mode": "placeholder_media",
                "ffmpeg_available": bool(self.ffmpeg_path),
                "playable_video_count": playable_video_count,
                "placeholder_file_count": placeholder_file_count,
                "shot_video_paths": [str(path.relative_to(project_dir)) for path in shot_video_paths],
                "note": "ffmpeg 可用时输出 mp4；ffmpeg 不可用时输出标准库 AVI 假视频，仍可作为可播放占位片段。",
            },
        )
        assets.append(self._asset("placeholder_media_manifest", media_manifest_path, project_dir, plan.project_title, {}))
        return PlaceholderShotMediaResult(
            shot_video_paths=shot_video_paths,
            generated_assets=assets,
            continuity_report=continuity_report,
            ffmpeg_available=bool(self.ffmpeg_path),
            playable_video_count=playable_video_count,
            placeholder_file_count=placeholder_file_count,
        )

    def to_shot_generation_result(self, media_result: PlaceholderShotMediaResult) -> ShotGenerationResult:
        stage_status = "completed" if media_result.shot_video_paths else "skipped"
        if media_result.placeholder_file_count:
            detail = "已生成本地占位镜头文件、首尾帧和连续性报告；部分多段镜头因 ffmpeg 不可用仅复制首段作为占位总镜头。"
        else:
            detail = "已生成本地可播放占位视频、首尾帧和连续性报告。ffmpeg 不可用时使用标准库 AVI 假视频。"
        return ShotGenerationResult(
            shot_video_paths=media_result.shot_video_paths,
            generated_assets=media_result.generated_assets,
            stage_record=ProductionStageRecord(
                stage_name="placeholder_shot_generation",
                status=stage_status,
                detail=detail,
                metadata={
                    "mode": "placeholder_media",
                    "ffmpeg_available": media_result.ffmpeg_available,
                    "video_count": len(media_result.shot_video_paths),
                    "playable_video_count": media_result.playable_video_count,
                    "placeholder_file_count": media_result.placeholder_file_count,
                },
            ),
            continuity_report=media_result.continuity_report,
        )

    def generate_transition_images(
        self,
        *,
        project_id: str,
        project_dir: Path,
        assembly_plan: AssemblyPlan,
        request: DramaProjectRequest,
    ) -> tuple[list[Path], list[GeneratedAsset]]:
        transition_paths: list[Path] = []
        assets: list[GeneratedAsset] = []
        for transition in assembly_plan.transitions[: request.render_transition_limit]:
            output_path = self.repository.transition_image_path(project_id, transition.transition_no)
            self._write_placeholder_png(
                output_path,
                title=f"转场{transition.transition_no:02d}",
                subtitle=transition.summary or transition.visual_prompt or transition.transition_type,
                accent=self._accent_for_index(transition.transition_no + 30),
            )
            transition_paths.append(output_path)
            assets.append(
                self._asset(
                    "placeholder_transition_image",
                    output_path,
                    project_dir,
                    f"transition_{transition.transition_no:02d}",
                    {
                        "transition_no": transition.transition_no,
                        "from_shot_no": transition.from_shot_no,
                        "to_shot_no": transition.to_shot_no,
                    },
                )
            )
        return transition_paths, assets

    def _write_placeholder_video(self, output_path: Path, *, duration_seconds: int, shot_no: int, segment_no: int) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ffmpeg_path:
            write_placeholder_avi(output_path, duration_seconds=duration_seconds, seed=shot_no * 10 + segment_no)
            return True

        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={self._ffmpeg_color_for_index(shot_no + segment_no)}:s=1280x720:d={max(1, int(duration_seconds))}",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=48000",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True

    def _build_placeholder_shot_video(self, *, segment_paths: list[Path], output_path: Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not segment_paths:
            return False
        if len(segment_paths) == 1:
            shutil.copyfile(segment_paths[0], output_path)
            return True
        if not self.ffmpeg_path:
            shutil.copyfile(segment_paths[0], output_path)
            return False
        concat_list = output_path.with_name(f"{output_path.stem}_placeholder_segments.txt")
        concat_list.write_text("\n".join(f"file '{path.as_posix()}'" for path in segment_paths), encoding="utf-8")
        command = [self.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True

    def _placeholder_segment_video_path(self, project_id: str, shot_no: int, segment_no: int) -> Path:
        if self.ffmpeg_path:
            return self.repository.shot_segment_video_path(project_id, shot_no, segment_no)
        return self.repository.placeholder_shot_segment_video_path(project_id, shot_no, segment_no)

    def _placeholder_shot_video_path(self, project_id: str, shot_no: int) -> Path:
        if self.ffmpeg_path:
            return self.repository.shot_video_path(project_id, shot_no)
        return self.repository.placeholder_shot_video_path(project_id, shot_no)

    @staticmethod
    def _build_continuity_check(
        *,
        shot_no: int,
        segment_no: int,
        project_dir: Path,
        first_frame_path: Path,
        end_frame_path: Path,
        tail_frame_path: Path,
        playable: bool,
    ) -> ContinuityCheckResult:
        return ContinuityCheckResult(
            shot_no=shot_no,
            segment_no=segment_no,
            attempt_no=1,
            passed=True,
            score=100.0,
            issues=[],
            metrics={
                "mode": "placeholder_media",
                "first_frame_source": str(first_frame_path.relative_to(project_dir)),
                "target_end_frame": str(end_frame_path.relative_to(project_dir)),
                "tail_frame": str(tail_frame_path.relative_to(project_dir)),
                "playable_video": playable,
            },
        )

    @staticmethod
    def _asset(asset_type: str, path: Path, project_dir: Path, source_name: str, metadata: dict) -> GeneratedAsset:
        payload = dict(metadata)
        payload["placeholder_media"] = True
        return GeneratedAsset(
            asset_type=asset_type,
            relative_path=str(path.relative_to(project_dir)),
            source_name=source_name,
            metadata=payload,
        )

    @staticmethod
    def _write_placeholder_png(output_path: Path, *, title: str, subtitle: str, accent: tuple[int, int, int]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1280, 720
        image = Image.new("RGB", (width, height), (18, 20, 24))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(1, height - 1)
            shade = int(22 + ratio * 36)
            draw.line([(0, y), (width, y)], fill=(shade, shade + 2, shade + 8))
        draw.rectangle([0, 0, width, 96], fill=accent)
        draw.rectangle([72, 150, width - 72, height - 90], outline=accent, width=6)
        font_title = PlaceholderMediaService._load_font(46)
        font_body = PlaceholderMediaService._load_font(30)
        draw.text((92, 24), title, fill=(255, 255, 255), font=font_title)
        draw.multiline_text((110, 220), PlaceholderMediaService._wrap_text(subtitle, max_chars=28), fill=(235, 238, 242), font=font_body, spacing=14)
        draw.text((110, height - 145), "本地占位图：用于全流程演练和连续性检查", fill=(200, 208, 218), font=font_body)
        image.save(output_path)

    @staticmethod
    def _load_font(size: int):
        from PIL import ImageFont

        for font_path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/arial.ttf"):
            if Path(font_path).is_file():
                return ImageFont.truetype(font_path, size=size)
        return ImageFont.load_default()

    @staticmethod
    def _wrap_text(text: str, *, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return "\n".join(text[index : index + max_chars] for index in range(0, min(len(text), max_chars * 4), max_chars))

    @staticmethod
    def _accent_for_index(index: int) -> tuple[int, int, int]:
        palette = [(34, 112, 147), (132, 82, 47), (92, 117, 74), (144, 54, 74), (86, 91, 150), (148, 115, 42)]
        return palette[(index - 1) % len(palette)]

    @staticmethod
    def _ffmpeg_color_for_index(index: int) -> str:
        palette = ["0x22384a", "0x4a2f25", "0x33462f", "0x4a2635", "0x30345d"]
        return palette[(index - 1) % len(palette)]
