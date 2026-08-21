from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

from projects.ai_short_drama.backend.app.services.placeholder_video_writer import write_placeholder_avi


class PlaceholderVideoProvider:
    """替代 Seedance 的本地假视频 provider，保留视频生成调用接口。"""

    is_placeholder_video = True

    def __init__(self) -> None:
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.output_suffix = ".mp4" if self.ffmpeg_path else ".avi"
        self._tasks: dict[str, dict] = {}

    def create_video_task(
        self,
        *,
        prompt: str,
        first_frame_local_path: Path,
        last_frame_local_path: Path | None = None,
        reference_image_local_paths: list[Path] | None = None,
        ratio: str | None = None,
        duration_seconds: int | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        return_last_frame: bool | None = None,
    ) -> str:
        task_id = f"placeholder-video-{len(self._tasks) + 1:04d}"
        self._tasks[task_id] = {
            "prompt": prompt,
            "first_frame_local_path": str(first_frame_local_path),
            "last_frame_local_path": str(last_frame_local_path) if last_frame_local_path else "",
            "reference_image_local_paths": [str(path) for path in reference_image_local_paths or []],
            "ratio": ratio,
            "duration_seconds": duration_seconds or 4,
            "resolution": resolution,
            "generate_audio": generate_audio,
            "return_last_frame": return_last_frame,
            "seed": len(self._tasks) + 1,
        }
        return task_id

    def wait_for_video_result(self, task_id: str, *, poll_interval_seconds: int = 8, timeout_seconds: int = 600) -> dict:
        if task_id not in self._tasks:
            raise RuntimeError(f"占位视频任务不存在: {task_id}")
        return {
            "status": "succeeded",
            "content": {
                "video_url": f"placeholder-video://{task_id}",
                "last_frame_url": f"placeholder-tail://{task_id}",
            },
            "meta_data": self._tasks[task_id],
        }

    def download_video(self, *, video_url: str, output_path: Path) -> Path:
        task = self._task_from_url(video_url, prefix="placeholder-video://")
        if self.ffmpeg_path and output_path.suffix.lower() == ".mp4":
            return self._write_placeholder_mp4(
                output_path,
                duration_seconds=int(task.get("duration_seconds") or 4),
                seed=int(task.get("seed") or 1),
            )
        return write_placeholder_avi(
            output_path,
            duration_seconds=int(task.get("duration_seconds") or 4),
            seed=int(task.get("seed") or 1),
        )

    def download_last_frame(self, *, last_frame_url: str, output_path: Path) -> Path:
        task = self._task_from_url(last_frame_url, prefix="placeholder-tail://")
        source_frame = Path(str(task.get("last_frame_local_path") or task.get("first_frame_local_path") or ""))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if source_frame.is_file():
            shutil.copyfile(source_frame, output_path)
        else:
            output_path.write_bytes(_MINIMAL_PNG_BYTES)
        return output_path

    @staticmethod
    def extract_video_url(video_result: dict) -> str | None:
        return video_result.get("content", {}).get("video_url")

    @staticmethod
    def extract_last_frame_url(video_result: dict) -> str | None:
        return video_result.get("content", {}).get("last_frame_url")

    def _task_from_url(self, url: str, *, prefix: str) -> dict:
        if not url.startswith(prefix):
            raise ValueError(f"占位视频 URL 格式不正确: {url}")
        task_id = url.removeprefix(prefix)
        if task_id not in self._tasks:
            raise RuntimeError(f"占位视频任务不存在: {task_id}")
        return self._tasks[task_id]

    def _write_placeholder_mp4(self, output_path: Path, *, duration_seconds: int, seed: int) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        color = self._ffmpeg_color_for_seed(seed)
        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=1280x720:d={max(1, int(duration_seconds))}",
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
        return output_path

    @staticmethod
    def _ffmpeg_color_for_seed(seed: int) -> str:
        palette = ["0x22384a", "0x4a2f25", "0x33462f", "0x4a2635", "0x30345d"]
        return palette[seed % len(palette)]


_MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p3lH3sAAAAASUVORK5CYII="
)
