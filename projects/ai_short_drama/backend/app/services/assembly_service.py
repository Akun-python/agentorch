from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import AssemblyPlan, ProductionStageRecord, ShortDramaPlan


class EpisodeAssemblyService:
    """生成本地成片装配清单，并在可用时调用 ffmpeg。"""

    def __init__(self) -> None:
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")

    def build_episode_package(
        self,
        *,
        project_dir: Path,
        plan: ShortDramaPlan,
        assembly_plan: AssemblyPlan,
        shot_video_paths: list[Path],
    ) -> tuple[Path, ProductionStageRecord, list[Path]]:
        exports_dir = Path(project_dir) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        transition_cards = self._write_transition_cards(exports_dir=exports_dir, assembly_plan=assembly_plan)
        package_path = exports_dir / "episode_assembly.json"
        package_payload = {
            "episode_title": assembly_plan.episode_title,
            "editing_style": assembly_plan.editing_style,
            "shot_videos": [str(path) for path in shot_video_paths],
            "transitions": [item.model_dump() for item in assembly_plan.transitions],
            "overlap_editing": self._build_overlap_editing_plan(assembly_plan),
            "transition_cards": [str(path) for path in transition_cards],
            "ffmpeg_available": bool(self.ffmpeg_path),
            "ffprobe_available": bool(self.ffprobe_path),
            "assembly_status": "ready_to_overlap_concat" if shot_video_paths and self.ffmpeg_path else "planning_only",
            "export_notes": assembly_plan.export_notes,
            "plan_summary": plan.episode_summary,
        }
        package_path.write_text(json.dumps(package_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        if not shot_video_paths:
            return (
                package_path,
                ProductionStageRecord(
                    stage_name="episode_assembly",
                    status="skipped",
                    detail="没有可用镜头视频，已仅生成装配清单",
                    metadata={"reason": "missing_shot_videos", "episode_package": str(package_path)},
                ),
                transition_cards,
            )

        if not self.ffmpeg_path:
            return (
                package_path,
                ProductionStageRecord(
                    stage_name="episode_assembly",
                    status="blocked",
                    detail="本机未安装 ffmpeg，已生成装配清单和转场卡片，暂无法自动拼接最终视频",
                    metadata={"episode_package": str(package_path)},
                ),
                transition_cards,
            )

        output_video = exports_dir / "episode_preview.mp4"
        concat_list = exports_dir / "concat_inputs.txt"
        concat_lines = []
        for path in shot_video_paths:
            concat_lines.append(f"file '{path.as_posix()}'")
        concat_list.write_text("\n".join(concat_lines), encoding="utf-8")

        command = self._build_ffmpeg_command(
            concat_list=concat_list,
            output_video=output_video,
            shot_video_paths=shot_video_paths,
            assembly_plan=assembly_plan,
        )
        subprocess.run(command, check=True, capture_output=True, text=True)
        return (
            package_path,
            ProductionStageRecord(
                stage_name="episode_assembly",
                status="completed",
                detail="已使用 ffmpeg 输出预览成片",
                metadata={"output_video": str(output_video), "episode_package": str(package_path)},
            ),
            transition_cards,
            )

    def _write_transition_cards(self, *, exports_dir: Path, assembly_plan: AssemblyPlan) -> list[Path]:
        transition_dir = exports_dir / "transition_cards"
        transition_dir.mkdir(parents=True, exist_ok=True)
        created_paths: list[Path] = []
        for transition in assembly_plan.transitions:
            card_path = transition_dir / f"transition_{transition.transition_no:02d}.txt"
            card_payload = {
                "transition_no": transition.transition_no,
                "from_shot_no": transition.from_shot_no,
                "to_shot_no": transition.to_shot_no,
                "transition_type": transition.transition_type,
                "duration_seconds": transition.duration_seconds,
                "overlap_seconds": transition.overlap_seconds,
                "audio_bridge": transition.audio_bridge,
                "summary": transition.summary,
                "visual_prompt": transition.visual_prompt,
            }
            card_path.write_text(json.dumps(card_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            created_paths.append(card_path)
        return created_paths

    @staticmethod
    def _build_overlap_editing_plan(assembly_plan: AssemblyPlan) -> list[dict]:
        return [
            {
                "from_shot_no": transition.from_shot_no,
                "to_shot_no": transition.to_shot_no,
                "transition_type": transition.transition_type,
                "duration_seconds": transition.duration_seconds,
                "overlap_seconds": transition.overlap_seconds,
                "audio_bridge": transition.audio_bridge,
                "summary": transition.summary,
            }
            for transition in assembly_plan.transitions
        ]

    def _build_ffmpeg_command(
        self,
        *,
        concat_list: Path,
        output_video: Path,
        shot_video_paths: list[Path],
        assembly_plan: AssemblyPlan,
    ) -> list[str]:
        if len(shot_video_paths) < 2 or not assembly_plan.transitions:
            return [
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
                str(output_video),
            ]

        # 复杂交叠需要重编码，先保守记录 overlap 方案，实际预览仍用 concat 保证稳定产物。
        return [
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
            str(output_video),
        ]
