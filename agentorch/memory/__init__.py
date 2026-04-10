"""Memory management primitives and default storage backends.

This package exposes the high-level MemoryManager plus the default in-memory
state store, SQLite-backed checkpoint and record stores, and composable
memory mechanisms.
"""

from .base import (
    MemoryBackend,
    MemoryDecayPolicy,
    MemoryGovernance,
    MemoryIndexPolicy,
    MemoryMechanism,
    MemoryPromotionPolicy,
    MemoryRecallPolicy,
)
from .bootstrap import bootstrap_memory_defaults
from .factory import (
    create_memory_backend,
    create_memory_decay_policy,
    create_memory_governance,
    create_memory_index_policy,
    create_memory_mechanism,
    create_memory_promotion_policy,
    create_memory_recall_policy,
)
from .governance import MGCMMemoryGovernance
from .manager import MemoryManager
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
    MemoryBackendRegistration,
    MemoryBackendRegistry,
    MemoryGovernanceRegistration,
    MemoryGovernanceRegistry,
    MemoryMechanismRegistration,
    MemoryMechanismRegistry,
    list_memory_backends,
    list_memory_decay_policies,
    list_memory_governance,
    list_memory_index_policies,
    list_memory_mechanisms,
    list_memory_promotion_policies,
    list_memory_recall_policies,
    register_memory_backend,
    register_memory_decay_policy,
    register_memory_governance,
    register_memory_index_policy,
    register_memory_mechanism,
    register_memory_promotion_policy,
    register_memory_recall_policy,
)
from .state import MemorySessionState
from .types import CollectiveMemoryRecord, EpisodicCapsule, MemoryRecord
from .backends import InMemoryStateStore, SQLiteCheckpointStore, SQLiteRecordStore

__all__ = [
    "InMemoryStateStore",
    "CollectiveMemoryRecord",
    "EpisodicCapsule",
    "EpisodicSaliencePromotionPolicy",
    "MGCMMemoryGovernance",
    "MemoryBackend",
    "MemoryBackendRegistration",
    "MemoryBackendRegistry",
    "MemoryDecayPolicy",
    "MemoryGovernance",
    "MemoryGovernanceRegistration",
    "MemoryGovernanceRegistry",
    "MemoryIndexPolicy",
    "MemoryMechanism",
    "MemoryMechanismRegistration",
    "MemoryMechanismRegistry",
    "MemoryManager",
    "MemoryPromotionPolicy",
    "MemoryRecallPolicy",
    "MemoryRecord",
    "MemorySessionState",
    "RelevanceOnlyDecayPolicy",
    "AgentLocalMemoryMechanism",
    "CollectiveMemoryMechanism",
    "RecordMemoryMechanism",
    "SceneFirstRecallPolicy",
    "SceneHashIndexPolicy",
    "SessionMemoryMechanism",
    "SharedNoteMemoryMechanism",
    "SQLiteCheckpointStore",
    "SQLiteRecordStore",
    "TemporalDecayMemoryMechanism",
    "ThreadSummaryMemoryMechanism",
    "WorkspaceMemoryMechanism",
    "bootstrap_memory_defaults",
    "create_memory_backend",
    "create_memory_decay_policy",
    "create_memory_governance",
    "create_memory_index_policy",
    "create_memory_mechanism",
    "create_memory_promotion_policy",
    "create_memory_recall_policy",
    "list_memory_backends",
    "list_memory_decay_policies",
    "list_memory_governance",
    "list_memory_index_policies",
    "list_memory_mechanisms",
    "list_memory_promotion_policies",
    "list_memory_recall_policies",
    "register_memory_backend",
    "register_memory_decay_policy",
    "register_memory_governance",
    "register_memory_index_policy",
    "register_memory_mechanism",
    "register_memory_promotion_policy",
    "register_memory_recall_policy",
]
