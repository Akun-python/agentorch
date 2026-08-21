from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm.auto import tqdm


def _now_text() -> str:
    """返回给人看的本地时间文本。"""

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class SuiteProgressContext:
    """实验进度上下文。

    同时写文本日志、JSONL 日志和 tqdm 进度条，便于长跑实验中途审计。
    """

    suite: str
    output_dir: Path
    total_steps: int
    initial_done: int = 0

    def __post_init__(self) -> None:
        """初始化输出目录、进度条和 suite_start 记录。"""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_dir / "run.log"
        self.jsonl_path = self.output_dir / "progress.jsonl"
        self._bar = tqdm(
            total=self.total_steps,
            initial=self.initial_done,
            desc=f"{self.suite}",
            dynamic_ncols=True,
            unit="step",
        )
        self._write_line(
            self.log_path,
            f"[{_now_text()}] suite_start suite={self.suite} total_steps={self.total_steps} resumed={self.initial_done}",
        )
        self._write_jsonl(
            {
                "timestamp": _now_text(),
                "event": "suite_start",
                "suite": self.suite,
                "total_steps": self.total_steps,
                "initial_done": self.initial_done,
            }
        )

    def log_case_start(self, *, run_round: int, case_id: str, method: str, variant: str) -> None:
        """记录单个 case 开始执行。"""

        message = f"r{run_round} | {method}/{variant} | {case_id}"
        self._bar.set_postfix_str(message)
        self._write_line(
            self.log_path,
            f"[{_now_text()}] case_start run_round={run_round} method={method} variant={variant} case_id={case_id}",
        )
        self._write_jsonl(
            {
                "timestamp": _now_text(),
                "event": "case_start",
                "suite": self.suite,
                "run_round": run_round,
                "method": method,
                "variant": variant,
                "case_id": case_id,
            }
        )

    def log_case_end(
        self,
        *,
        run_round: int,
        case_id: str,
        method: str,
        variant: str,
        judge_score: float,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        answer_total_tokens: int = 0,
        answer_duration_ms: float = 0.0,
        judge_total_tokens: int = 0,
        judge_duration_ms: float = 0.0,
        embedding_request_count: int = 0,
        embedding_text_count: int = 0,
        embedding_latency_ms: float = 0.0,
        latency_breakdown: dict[str, Any] | None = None,
    ) -> None:
        """记录单个 case 完成后的指标快照。"""

        self._bar.update(1)
        message = (
            f"r{run_round} | {method}/{variant} | score={judge_score:.2f} | "
            f"ret={latency_ms:.0f}ms | ans={answer_duration_ms:.0f}ms | "
            f"tok={input_tokens}/{output_tokens}/{answer_total_tokens}"
        )
        self._bar.set_postfix_str(message)
        self._write_line(
            self.log_path,
            f"[{_now_text()}] case_end run_round={run_round} method={method} variant={variant} "
            f"case_id={case_id} judge_score={judge_score:.4f} latency_ms={latency_ms:.4f} "
            f"input_tokens={input_tokens} output_tokens={output_tokens} answer_total_tokens={answer_total_tokens} "
            f"answer_duration_ms={answer_duration_ms:.4f} judge_total_tokens={judge_total_tokens} "
            f"judge_duration_ms={judge_duration_ms:.4f} embedding_request_count={embedding_request_count} "
            f"embedding_text_count={embedding_text_count} embedding_latency_ms={embedding_latency_ms:.4f} "
            f"latency_breakdown={json.dumps(latency_breakdown or {}, ensure_ascii=False, sort_keys=True)}",
        )
        self._write_jsonl(
            {
                "timestamp": _now_text(),
                "event": "case_end",
                "suite": self.suite,
                "run_round": run_round,
                "method": method,
                "variant": variant,
                "case_id": case_id,
                "judge_score": judge_score,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "answer_total_tokens": answer_total_tokens,
                "answer_duration_ms": answer_duration_ms,
                "judge_total_tokens": judge_total_tokens,
                "judge_duration_ms": judge_duration_ms,
                "embedding_request_count": embedding_request_count,
                "embedding_text_count": embedding_text_count,
                "embedding_latency_ms": embedding_latency_ms,
                "latency_breakdown": latency_breakdown or {},
                "completed_steps": self._bar.n,
                "total_steps": self.total_steps,
            }
        )

    def log_skip(self, *, run_round: int, case_id: str, method: str, variant: str) -> None:
        """断点恢复命中已完成记录时写入跳过日志。"""

        self._write_line(
            self.log_path,
            f"[{_now_text()}] case_skip run_round={run_round} method={method} variant={variant} case_id={case_id}",
        )
        self._write_jsonl(
            {
                "timestamp": _now_text(),
                "event": "case_skip",
                "suite": self.suite,
                "run_round": run_round,
                "method": method,
                "variant": variant,
                "case_id": case_id,
            }
        )

    def log_suite_end(self, *, record_count: int, aggregate_count: int) -> None:
        """关闭进度条并记录套件结束。"""

        self._bar.set_postfix_str("done")
        self._bar.close()
        self._write_line(
            self.log_path,
            f"[{_now_text()}] suite_end suite={self.suite} record_count={record_count} aggregate_count={aggregate_count}",
        )
        self._write_jsonl(
            {
                "timestamp": _now_text(),
                "event": "suite_end",
                "suite": self.suite,
                "record_count": record_count,
                "aggregate_count": aggregate_count,
            }
        )

    @staticmethod
    def log_root_event(root_dir: Path, *, event: str, payload: dict[str, Any]) -> None:
        """full 命令跨套件运行时写根目录级别日志。"""

        root_dir.mkdir(parents=True, exist_ok=True)
        line = {"timestamp": _now_text(), "event": event, **payload}
        text_path = root_dir / "full_run.log"
        jsonl_path = root_dir / "full_progress.jsonl"
        with text_path.open("a", encoding="utf-8") as handle:
            summary = " ".join(f"{key}={value}" for key, value in line.items())
            handle.write(summary + "\n")
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _write_line(path: Path, message: str) -> None:
        """追加一行普通文本日志。"""

        with path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    def _write_jsonl(self, payload: dict[str, Any]) -> None:
        """追加一行机器可读 JSONL 日志。"""

        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
