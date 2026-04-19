from __future__ import annotations

from .bootstrap import ensure_repo_root_on_path
from .config import HarnessConfig

ensure_repo_root_on_path()

from agentorch.config import MemoryConfig
from agentorch.memory import MemoryManager


def build_memory_manager(config: HarnessConfig) -> MemoryManager:
    config.ensure_runtime_layout()
    memory_root = config.agentorch_runtime_root
    return MemoryManager(
        config=MemoryConfig(
            checkpoint_path=memory_root / "codexharness_checkpoints.db",
            record_path=memory_root / "codexharness_records.db",
            persist_thread_messages=config.persist_thread_messages,
            thread_history_recall_limit=config.thread_history_recall_limit,
        )
    )
