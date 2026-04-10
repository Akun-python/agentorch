from __future__ import annotations

from .backends import InMemoryStateStore, SQLiteCheckpointStore, SQLiteRecordStore
from .governance import MGCMMemoryGovernance
from .mechanisms import (
    AgentLocalMemoryMechanism,
    CollectiveMemoryMechanism,
    RecordMemoryMechanism,
    SessionMemoryMechanism,
    SharedNoteMemoryMechanism,
    TemporalDecayMemoryMechanism,
    ThreadSummaryMemoryMechanism,
    WorkspaceMemoryMechanism,
)
from .policies import EpisodicSaliencePromotionPolicy, RelevanceOnlyDecayPolicy, SceneFirstRecallPolicy, SceneHashIndexPolicy
from .registry import (
    register_memory_backend,
    register_memory_decay_policy,
    register_memory_governance,
    register_memory_index_policy,
    register_memory_mechanism,
    register_memory_promotion_policy,
    register_memory_recall_policy,
)

_BOOTSTRAPPED = False


def bootstrap_memory_defaults(*, force: bool = False) -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED and not force:
        return
    register_memory_backend("in_memory_state_store", InMemoryStateStore)
    register_memory_backend("sqlite_checkpoint_store", SQLiteCheckpointStore)
    register_memory_backend("sqlite_record_store", SQLiteRecordStore)
    register_memory_governance("mgcm_governance", MGCMMemoryGovernance)
    register_memory_mechanism("session_memory", SessionMemoryMechanism)
    register_memory_mechanism("thread_summary_memory", ThreadSummaryMemoryMechanism)
    register_memory_mechanism("agent_local_memory", AgentLocalMemoryMechanism)
    register_memory_mechanism("workspace_memory", WorkspaceMemoryMechanism)
    register_memory_mechanism("shared_note_memory", SharedNoteMemoryMechanism)
    register_memory_mechanism("record_memory", RecordMemoryMechanism)
    register_memory_mechanism("collective_memory", CollectiveMemoryMechanism)
    register_memory_mechanism("temporal_decay_memory", TemporalDecayMemoryMechanism)
    register_memory_promotion_policy("episodic_salience", EpisodicSaliencePromotionPolicy)
    register_memory_index_policy("scene_hash", SceneHashIndexPolicy)
    register_memory_recall_policy("scene_first", SceneFirstRecallPolicy)
    register_memory_decay_policy("relevance_only", RelevanceOnlyDecayPolicy)
    _BOOTSTRAPPED = True
