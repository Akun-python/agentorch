from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from agentorch.knowledge import RagStrategyConfig, RetrievalMode
from agentorch.prompts import ChatPromptTemplate
from agentorch.reasoning.base import ReasoningStrategyConfig
from agentorch.security import PayloadBudgetConfig, RedactionConfig
from agentorch.skills import SkillRoutingConfig
from agentorch.strategies import (
    BaseContextStrategy,
    BaseCooperationStrategy,
    BaseLongHorizonStrategy,
    BaseMemoryGovernanceStrategy,
    ContextStrategyConfig,
    CooperationStrategyConfig,
    LongHorizonStrategyConfig,
    MemoryGovernanceStrategyConfig,
    resolve_orchestration_profile,
)


def _load_local_env(env_path: str | Path | None = None, *, overwrite: bool = False) -> None:
    path = Path(env_path or (Path.cwd() / ".env"))
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and (overwrite or key not in os.environ):
            os.environ[key] = value


def initialize_environment(env_path: str | Path | None = None, *, overwrite: bool = False) -> None:
    _load_local_env(env_path=env_path, overwrite=overwrite)


def validate_supported_python(
    version_info: tuple[int, int] | None = None,
    *,
    minimum: tuple[int, int] = (3, 10),
) -> None:
    resolved = version_info or (sys.version_info.major, sys.version_info.minor)
    if resolved >= minimum:
        return
    current = f"{resolved[0]}.{resolved[1]}"
    required = f"{minimum[0]}.{minimum[1]}"
    raise RuntimeError(
        "environment_error: agentorch requires Python "
        f"{required}+ but detected Python {current}. "
        "Use `py -3.13` or `py -3.14`, and run tests with "
        "`$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; py -3.13 -m pytest -q`."
    )


def _should_auto_load_env() -> bool:
    return os.getenv("AGENTORCH_AUTO_LOAD_ENV", "").strip().lower() in {"1", "true", "yes", "on"}


if _should_auto_load_env():
    _load_local_env()


def _normalize_openai_base_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned[: -len("/chat/completions")]
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return cleaned
    return None


def _get_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")


def _get_base_url() -> str | None:
    return _normalize_openai_base_url(os.getenv("OPENAI_BASE_URL") or os.getenv("BASE_URL"))


def _get_vision_model() -> str | None:
    value = os.getenv("OPENAI_VISION_MODEL") or os.getenv("VISION_MODEL") or os.getenv("IMAGE_MODEL")
    if not value:
        return None
    return value.strip() or None


def _get_brave_api_key() -> str | None:
    return os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY")


class ModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    vision_model: str | None = Field(default_factory=_get_vision_model)
    api_key: str | None = Field(default_factory=_get_api_key)
    base_url: str | None = Field(default_factory=_get_base_url)
    endpoint_path: str = "/chat/completions"
    auth_scheme: str = "Bearer"
    headers: dict[str, str] = Field(default_factory=dict)
    provider_options: dict[str, object] = Field(default_factory=dict)
    max_tokens: int | None = 2048
    timeout: float = 60.0
    max_retries: int = 2
    retry_base_delay: float = 2.0
    retry_max_delay: float = 30.0
    retry_jitter: float = 0.25
    min_request_interval: float = 0.0
    temperature: float | None = None

    @classmethod
    def from_any(cls, value: "ModelConfig | dict[str, object] | str | None", **overrides: object) -> "ModelConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, str):
            base = cls(model=value)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base


class MemoryMechanismConfig(BaseModel):
    kind: str
    enabled: bool = True
    config: dict[str, object] = Field(default_factory=dict)


class MemoryConfig(BaseModel):
    checkpoint_path: Path = Path(".agentorch/checkpoints.db")
    record_path: Path = Path(".agentorch/records.db")
    message_window: int = 12
    summary_window: int = 40
    persist_thread_messages: bool = True
    thread_history_recall_limit: int = 4
    validate_composition: bool = True
    allow_partial_mechanisms: bool = False
    required_operations: list[str] = Field(default_factory=list)
    redaction: RedactionConfig = Field(default_factory=RedactionConfig)
    summary_only_persistence: bool = False
    max_record_content_chars: int = 8000
    max_record_metadata_chars: int = 4000
    truncate_thread_messages_before_persist: bool = True
    persist_full_prompt_text: bool = False
    mechanisms: list[MemoryMechanismConfig] = Field(
        default_factory=lambda: [
            MemoryMechanismConfig(kind="session_memory"),
            MemoryMechanismConfig(kind="thread_summary_memory"),
            MemoryMechanismConfig(kind="agent_local_memory"),
            MemoryMechanismConfig(kind="workspace_memory"),
            MemoryMechanismConfig(kind="shared_note_memory"),
            MemoryMechanismConfig(kind="record_memory"),
            MemoryMechanismConfig(kind="collective_memory"),
        ]
    )


class SandboxConfig(BaseModel):
    enabled: bool = True
    default_timeout: float = 30.0
    allowed_paths: list[Path] = Field(default_factory=list)
    command_allowlist: list[str] = Field(default_factory=list)
    command_blocklist: list[str] = Field(default_factory=list)
    allow_shell: bool = False


class ObservabilityConfig(BaseModel):
    enabled: bool = False
    store_backend: Literal["sqlite"] = "sqlite"
    sqlite_path: Path = Path(".agentorch/observability.db")
    console_mode: Literal["silent", "important_only", "all"] = "silent"
    capture_todos: bool = True
    redaction: RedactionConfig = Field(default_factory=RedactionConfig)
    trace_payload_budget: PayloadBudgetConfig = Field(default_factory=PayloadBudgetConfig)

    @classmethod
    def from_any(cls, value: "ObservabilityConfig | dict[str, object] | None") -> "ObservabilityConfig":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        return cls.model_validate(value)


class RuntimeConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    system_prompt: str = (
        "You are a capable and careful agent. Use tools when they improve accuracy, "
        "stay concise, and return structured results when requested."
    )
    prompt_template: ChatPromptTemplate | None = None
    max_steps: int = 8
    auto_select_skills: bool = True
    skill_routing: SkillRoutingConfig | None = Field(default_factory=SkillRoutingConfig)
    parser_retry_limit: int = 1
    enable_retrieval: bool = False
    reasoning_strategy: ReasoningStrategyConfig | None = None
    orchestration_profile: str | None = None
    context_strategy: ContextStrategyConfig | BaseContextStrategy | None = None
    long_horizon_strategy: LongHorizonStrategyConfig | BaseLongHorizonStrategy | None = None
    cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | None = None
    memory_governance_strategy: MemoryGovernanceStrategyConfig | BaseMemoryGovernanceStrategy | None = None
    max_retrieved_chunks: int = 5
    retrieval_mode: RetrievalMode = RetrievalMode.OFF
    rag_strategy: RagStrategyConfig | None = None
    retrieval_backend: str = "deliberative"
    retrieval_auto_mode: Literal["off", "assist", "required"] = "assist"
    retrieval_allowed_source_types: list[str] = Field(default_factory=list)
    retrieval_allowed_file_types: list[str] = Field(default_factory=list)
    retrieval_budget_steps: int = 3
    retrieval_budget_documents: int = 8
    retrieval_return_mode: Literal["context_only", "report", "both"] = "both"
    default_knowledge_scope: list[str] = Field(default_factory=list)
    max_delegation_depth: int = 2
    enable_parallel_tasks: bool = False
    observability: ObservabilityConfig | None = None
    unsafe_export: bool = False
    tool_output_budget: PayloadBudgetConfig = Field(default_factory=lambda: PayloadBudgetConfig(max_total_chars=8000, max_string_chars=2000))
    redaction: RedactionConfig = Field(default_factory=RedactionConfig)

    @model_validator(mode="before")
    @classmethod
    def _normalize_nested_configs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        profile_name = normalized.get("orchestration_profile")
        if profile_name:
            profile = resolve_orchestration_profile(profile_name)
            for key, value in profile.items():
                if key not in normalized or normalized[key] is None:
                    normalized[key] = value
        if "rag_strategy" in normalized and normalized["rag_strategy"] is not None:
            normalized["rag_strategy"] = RagStrategyConfig.from_any(normalized["rag_strategy"])
        if "reasoning_strategy" in normalized and normalized["reasoning_strategy"] is not None:
            normalized["reasoning_strategy"] = ReasoningStrategyConfig.from_any(normalized["reasoning_strategy"])
        if "skill_routing" in normalized and normalized["skill_routing"] is not None:
            normalized["skill_routing"] = SkillRoutingConfig.from_any(normalized["skill_routing"])
        if "context_strategy" in normalized and normalized["context_strategy"] is not None:
            if not isinstance(normalized["context_strategy"], BaseContextStrategy):
                normalized["context_strategy"] = ContextStrategyConfig.from_any(normalized["context_strategy"])
        if "long_horizon_strategy" in normalized and normalized["long_horizon_strategy"] is not None:
            if not isinstance(normalized["long_horizon_strategy"], BaseLongHorizonStrategy):
                normalized["long_horizon_strategy"] = LongHorizonStrategyConfig.from_any(normalized["long_horizon_strategy"])
        if "cooperation_strategy" in normalized and normalized["cooperation_strategy"] is not None:
            if not isinstance(normalized["cooperation_strategy"], BaseCooperationStrategy):
                normalized["cooperation_strategy"] = CooperationStrategyConfig.from_any(normalized["cooperation_strategy"])
        if "memory_governance_strategy" in normalized and normalized["memory_governance_strategy"] is not None:
            if not isinstance(normalized["memory_governance_strategy"], BaseMemoryGovernanceStrategy):
                normalized["memory_governance_strategy"] = MemoryGovernanceStrategyConfig.from_any(normalized["memory_governance_strategy"])
        if "observability" in normalized and normalized["observability"] is not None:
            normalized["observability"] = ObservabilityConfig.from_any(normalized["observability"])
        if "redaction" in normalized and normalized["redaction"] is not None:
            normalized["redaction"] = RedactionConfig.from_any(normalized["redaction"])
        if "tool_output_budget" in normalized and normalized["tool_output_budget"] is not None:
            normalized["tool_output_budget"] = PayloadBudgetConfig.from_any(normalized["tool_output_budget"])
        return normalized

    @classmethod
    def from_any(cls, value: "RuntimeConfig | dict[str, object] | None", **overrides: object) -> "RuntimeConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    @classmethod
    def agent(
        cls,
        *,
        system_prompt: str | None = None,
        rag: RagStrategyConfig | str | dict[str, object] | None = None,
        reasoning: ReasoningStrategyConfig | str | dict[str, object] | None = None,
        orchestration_profile: str | None = None,
        context: ContextStrategyConfig | BaseContextStrategy | str | dict[str, object] | None = None,
        context_strategy: ContextStrategyConfig | BaseContextStrategy | str | dict[str, object] | None = None,
        long_horizon_strategy: LongHorizonStrategyConfig | BaseLongHorizonStrategy | str | dict[str, object] | None = None,
        cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | str | dict[str, object] | None = None,
        memory_governance_strategy: MemoryGovernanceStrategyConfig | BaseMemoryGovernanceStrategy | str | dict[str, object] | None = None,
        observability: ObservabilityConfig | dict[str, object] | None = None,
        prompt_template: ChatPromptTemplate | None = None,
        skill_routing: SkillRoutingConfig | str | dict[str, object] | None = None,
        default_knowledge_scope: list[str] | None = None,
        **kwargs: object,
    ) -> "RuntimeConfig":
        rag_strategy = RagStrategyConfig.from_any(rag) if rag is not None else None
        context_value = context_strategy or context
        if isinstance(context_value, BaseContextStrategy):
            resolved_context = context_value
        else:
            resolved_context = ContextStrategyConfig.from_any(context_value) if context_value is not None else None
        payload: dict[str, object] = {
            "system_prompt": system_prompt or cls().system_prompt,
            "prompt_template": prompt_template,
            "orchestration_profile": orchestration_profile,
            "rag_strategy": rag_strategy,
            "enable_retrieval": rag_strategy is not None and rag_strategy.mode != "off",
            "reasoning_strategy": ReasoningStrategyConfig.from_any(reasoning) if reasoning is not None else None,
            "default_knowledge_scope": list(default_knowledge_scope or []),
            **kwargs,
        }
        if skill_routing is not None:
            payload["skill_routing"] = SkillRoutingConfig.from_any(skill_routing)
        if resolved_context is not None:
            payload["context_strategy"] = resolved_context
        if long_horizon_strategy is not None:
            payload["long_horizon_strategy"] = (
                long_horizon_strategy
                if isinstance(long_horizon_strategy, BaseLongHorizonStrategy)
                else LongHorizonStrategyConfig.from_any(long_horizon_strategy)
            )
        if cooperation_strategy is not None:
            payload["cooperation_strategy"] = (
                cooperation_strategy
                if isinstance(cooperation_strategy, BaseCooperationStrategy)
                else CooperationStrategyConfig.from_any(cooperation_strategy)
            )
        if memory_governance_strategy is not None:
            payload["memory_governance_strategy"] = (
                memory_governance_strategy
                if isinstance(memory_governance_strategy, BaseMemoryGovernanceStrategy)
                else MemoryGovernanceStrategyConfig.from_any(memory_governance_strategy)
            )
        if observability is not None:
            payload["observability"] = ObservabilityConfig.from_any(observability)
        return cls(**payload)

    @classmethod
    def workflow(
        cls,
        *,
        rag: RagStrategyConfig | str | dict[str, object] | None = None,
        reasoning: ReasoningStrategyConfig | str | dict[str, object] | None = None,
        orchestration_profile: str | None = None,
        context: ContextStrategyConfig | BaseContextStrategy | str | dict[str, object] | None = None,
        context_strategy: ContextStrategyConfig | BaseContextStrategy | str | dict[str, object] | None = None,
        long_horizon_strategy: LongHorizonStrategyConfig | BaseLongHorizonStrategy | str | dict[str, object] | None = None,
        cooperation_strategy: CooperationStrategyConfig | BaseCooperationStrategy | str | dict[str, object] | None = None,
        memory_governance_strategy: MemoryGovernanceStrategyConfig | BaseMemoryGovernanceStrategy | str | dict[str, object] | None = None,
        observability: ObservabilityConfig | dict[str, object] | None = None,
        skill_routing: SkillRoutingConfig | str | dict[str, object] | None = None,
        **kwargs: object,
    ) -> "RuntimeConfig":
        base = cls.agent(
            rag=rag,
            reasoning=reasoning,
            orchestration_profile=orchestration_profile,
            context=context,
            context_strategy=context_strategy,
            long_horizon_strategy=long_horizon_strategy,
            cooperation_strategy=cooperation_strategy,
            memory_governance_strategy=memory_governance_strategy,
            observability=observability,
            skill_routing=skill_routing,
            **kwargs,
        )
        return base.model_copy(update={"retrieval_mode": RetrievalMode.EXPLICIT_STEP})
