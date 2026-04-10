from .bootstrap import bootstrap_memory_defaults
from .registry import create_memory_backend as _create_memory_backend
from .registry import create_memory_decay_policy as _create_memory_decay_policy
from .registry import create_memory_governance as _create_memory_governance
from .registry import create_memory_index_policy as _create_memory_index_policy
from .registry import create_memory_mechanism as _create_memory_mechanism
from .registry import create_memory_promotion_policy as _create_memory_promotion_policy
from .registry import create_memory_recall_policy as _create_memory_recall_policy


def create_memory_backend(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_backend(kind, **kwargs)


def create_memory_governance(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_governance(kind, **kwargs)


def create_memory_mechanism(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_mechanism(kind, **kwargs)


def create_memory_promotion_policy(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_promotion_policy(kind, **kwargs)


def create_memory_index_policy(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_index_policy(kind, **kwargs)


def create_memory_recall_policy(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_recall_policy(kind, **kwargs)


def create_memory_decay_policy(kind: str, **kwargs):
    bootstrap_memory_defaults()
    return _create_memory_decay_policy(kind, **kwargs)


__all__ = [
    "create_memory_backend",
    "create_memory_decay_policy",
    "create_memory_governance",
    "create_memory_index_policy",
    "create_memory_mechanism",
    "create_memory_promotion_policy",
    "create_memory_recall_policy",
]
