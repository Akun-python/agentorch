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
    ContextPolicy,
    CoordinationPolicy,
    MemoryEvaluator,
    MemoryPolicy,
    RoutePlanner,
    ContextSelector,
    StatePolicy,
)

DEFAULT_CHAT_ENDPOINT_PATH = "/chat/completions"
DEFAULT_EMBEDDING_ENDPOINT_PATH = "/embeddings"
DEFAULT_SPEECH_ENDPOINT_PATH = "/audio/speech"
DEFAULT_SPEECH_FORMAT = "mp3"
DEFAULT_SPEECH_SPEED = 1.0
DEFAULT_IMAGE_ASPECT_RATIO = "16:9"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_IMAGE_TIMEOUT = 300.0


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


def _normalize_endpoint_path(value: str | None, *, default: str) -> str:
    cleaned = (value or default).strip() or default
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def _normalize_provider_base_url(value: str | None, *, endpoint_path: str) -> str | None:
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    normalized_endpoint = _normalize_endpoint_path(endpoint_path, default=endpoint_path)
    if cleaned.endswith(normalized_endpoint):
        return cleaned[: -len(normalized_endpoint)]
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return cleaned
    return None


def _normalize_openai_base_url(value: str | None) -> str | None:
    return _normalize_provider_base_url(value, endpoint_path=DEFAULT_CHAT_ENDPOINT_PATH)


def _normalize_image_base_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    for suffix in ("/v1/chat/completions", "/chat/completions"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return cleaned
    return None


def _get_api_key() -> str | None:
    return _get_first_env("OPENAI_API_KEY")


def _get_base_url() -> str | None:
    return _normalize_openai_base_url(_get_first_env("OPENAI_BASE_URL"))


def _get_first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _get_bool_env(*names: str, default: bool) -> bool:
    value = _get_first_env(*names)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_float_env(*names: str, default: float) -> float:
    value = _get_first_env(*names)
    if value is None:
        return default
    return float(value)


def _get_int_env(*names: str) -> int | None:
    value = _get_first_env(*names)
    if value is None:
        return None
    return int(value)


def _get_csv_env(*names: str) -> list[str]:
    value = _get_first_env(*names)
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_embedding_api_key() -> str | None:
    return _get_first_env("OPENAI_EMBEDDING_API_KEY") or _get_api_key()


def _get_embedding_base_url() -> str | None:
    explicit = _get_first_env("OPENAI_EMBEDDING_BASE_URL")
    if explicit:
        return _normalize_provider_base_url(explicit, endpoint_path=DEFAULT_EMBEDDING_ENDPOINT_PATH)
    return _get_base_url()


def _get_embedding_model() -> str | None:
    return _get_first_env("OPENAI_EMBEDDING_MODEL")


def _get_embedding_dimensions() -> int | None:
    return _get_int_env("OPENAI_EMBEDDING_DIMENSIONS")


def _get_speech_api_key() -> str | None:
    return _get_first_env("OPENAI_TTS_API_KEY") or _get_api_key()


def _get_speech_base_url() -> str | None:
    explicit = os.getenv("OPENAI_TTS_BASE_URL")
    if explicit:
        return _normalize_provider_base_url(explicit, endpoint_path=DEFAULT_SPEECH_ENDPOINT_PATH)
    return _get_base_url()


def _get_speech_model() -> str | None:
    return _get_first_env("OPENAI_TTS_MODEL")


def _get_speech_voice() -> str | None:
    return _get_first_env("OPENAI_TTS_VOICE")


def _get_speech_format() -> str:
    value = os.getenv("OPENAI_TTS_FORMAT")
    return value.strip().lower() if value and value.strip() else DEFAULT_SPEECH_FORMAT


def _get_speech_speed() -> float:
    value = os.getenv("OPENAI_TTS_SPEED")
    if value is None or not value.strip():
        return DEFAULT_SPEECH_SPEED
    return float(value.strip())


def _get_image_api_key() -> str | None:
    return _get_first_env("OPENAI_IMAGE_API_KEY") or _get_api_key()


def _get_image_base_url() -> str | None:
    return _normalize_image_base_url(_get_first_env("OPENAI_IMAGE_BASE_URL"))


def _get_image_explicit_url() -> str | None:
    return _get_first_env(
        "OPENAI_IMAGE_EXPLICIT_URL",
        "OPENAI_IMAGE_URL",
    )


def _get_image_model() -> str | None:
    return _get_first_env("OPENAI_IMAGE_MODEL")


def _get_image_aspect_ratio() -> str:
    return _get_first_env("OPENAI_IMAGE_ASPECT_RATIO") or DEFAULT_IMAGE_ASPECT_RATIO


def _get_image_size() -> str:
    return _get_first_env("OPENAI_IMAGE_SIZE") or DEFAULT_IMAGE_SIZE


def _get_image_timeout() -> float:
    return _get_float_env("OPENAI_IMAGE_TIMEOUT", default=DEFAULT_IMAGE_TIMEOUT)


def _get_image_fallback_models() -> list[str]:
    return _get_csv_env("OPENAI_IMAGE_FALLBACK_MODELS")


def _get_image_retry_without_proxy() -> bool:
    return _get_bool_env("OPENAI_IMAGE_RETRY_WITHOUT_PROXY", default=True)


def _get_image_disable_env_proxy() -> bool:
    return _get_bool_env("OPENAI_IMAGE_DISABLE_ENV_PROXY", default=False)


def _get_video_api_key() -> str | None:
    return _get_first_env("OPENAI_VIDEO_API_KEY") or _get_api_key()


def _get_video_base_url() -> str | None:
    explicit = _get_first_env("OPENAI_VIDEO_BASE_URL")
    if explicit:
        return _normalize_openai_base_url(explicit)
    return _get_base_url()


def _get_video_model() -> str | None:
    return _get_first_env("OPENAI_VIDEO_MODEL")


def _get_video_disable_env_proxy() -> bool:
    return _get_bool_env("OPENAI_VIDEO_DISABLE_ENV_PROXY", default=True)


def _get_vision_model() -> str | None:
    return _get_first_env("OPENAI_VISION_MODEL")


def _get_brave_api_key() -> str | None:
    return os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY")


class ModelConfig(BaseModel):
    provider: str = "openai"
    model: str | None = None
    vision_model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    endpoint_path: str = DEFAULT_CHAT_ENDPOINT_PATH
    auth_scheme: str = "Bearer"
    headers: dict[str, str] = Field(default_factory=dict)
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_endpoint_path: str = DEFAULT_EMBEDDING_ENDPOINT_PATH
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    speech_api_key: str | None = None
    speech_base_url: str | None = None
    speech_endpoint_path: str = DEFAULT_SPEECH_ENDPOINT_PATH
    speech_model: str | None = None
    speech_voice: str | None = None
    speech_format: str = DEFAULT_SPEECH_FORMAT
    speech_speed: float = DEFAULT_SPEECH_SPEED
    image_api_key: str | None = None
    image_base_url: str | None = None
    image_explicit_url: str | None = None
    image_model: str | None = None
    image_aspect_ratio: str = DEFAULT_IMAGE_ASPECT_RATIO
    image_size: str = DEFAULT_IMAGE_SIZE
    image_timeout: float = DEFAULT_IMAGE_TIMEOUT
    image_fallback_models: list[str] = Field(default_factory=list)
    image_retry_without_proxy: bool = True
    image_disable_env_proxy: bool = False
    video_api_key: str | None = None
    video_base_url: str | None = None
    video_model: str | None = None
    video_disable_env_proxy: bool = True
    provider_options: dict[str, object] = Field(default_factory=dict)
    max_tokens: int | None = 2048
    timeout: float = 60.0
    max_retries: int = 2
    retry_base_delay: float = 2.0
    retry_max_delay: float = 30.0
    retry_jitter: float = 0.25
    min_request_interval: float = 0.0
    temperature: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_env_backed_defaults(cls, data: object) -> object:
        if data is None:
            raw: dict[str, object] = {}
        elif isinstance(data, cls):
            return data
        elif isinstance(data, dict):
            raw = dict(data)
        else:
            return data

        explicit = set(raw.keys())
        resolved = dict(raw)

        def set_if_missing(field_name: str, value: object) -> None:
            if field_name not in explicit and value is not None:
                resolved[field_name] = value

        set_if_missing("vision_model", _get_vision_model())
        set_if_missing("api_key", _get_api_key())
        set_if_missing("base_url", _get_base_url())

        base_api_key = resolved.get("api_key")
        base_url = resolved.get("base_url")

        if "embedding_api_key" not in explicit:
            set_if_missing(
                "embedding_api_key",
                base_api_key if "api_key" in explicit else (_get_first_env("OPENAI_EMBEDDING_API_KEY") or base_api_key),
            )
        if "embedding_base_url" not in explicit:
            set_if_missing(
                "embedding_base_url",
                base_url if "base_url" in explicit else (_get_embedding_base_url() or base_url),
            )
        set_if_missing("embedding_model", _get_embedding_model())
        set_if_missing("embedding_dimensions", _get_embedding_dimensions())

        if "speech_api_key" not in explicit:
            set_if_missing(
                "speech_api_key",
                base_api_key if "api_key" in explicit else (_get_first_env("OPENAI_TTS_API_KEY") or base_api_key),
            )
        if "speech_base_url" not in explicit:
            set_if_missing(
                "speech_base_url",
                base_url if "base_url" in explicit else (_get_speech_base_url() or base_url),
            )
        set_if_missing("speech_model", _get_speech_model())
        set_if_missing("speech_voice", _get_speech_voice())
        set_if_missing("speech_format", _get_speech_format())
        set_if_missing("speech_speed", _get_speech_speed())

        if "image_api_key" not in explicit:
            set_if_missing(
                "image_api_key",
                base_api_key if "api_key" in explicit else (_get_first_env("OPENAI_IMAGE_API_KEY") or base_api_key),
            )
        set_if_missing("image_base_url", _get_image_base_url())
        set_if_missing("image_explicit_url", _get_image_explicit_url())
        set_if_missing("image_model", _get_image_model())
        set_if_missing("image_aspect_ratio", _get_image_aspect_ratio())
        set_if_missing("image_size", _get_image_size())
        set_if_missing("image_timeout", _get_image_timeout())
        if "image_fallback_models" not in explicit:
            resolved["image_fallback_models"] = list(_get_image_fallback_models())
        set_if_missing("image_retry_without_proxy", _get_image_retry_without_proxy())
        set_if_missing("image_disable_env_proxy", _get_image_disable_env_proxy())

        if "video_api_key" not in explicit:
            set_if_missing(
                "video_api_key",
                base_api_key if "api_key" in explicit else (_get_first_env("OPENAI_VIDEO_API_KEY") or base_api_key),
            )
        if "video_base_url" not in explicit:
            set_if_missing(
                "video_base_url",
                base_url if "base_url" in explicit else (_get_video_base_url() or base_url),
            )
        set_if_missing("video_model", _get_video_model())
        set_if_missing("video_disable_env_proxy", _get_video_disable_env_proxy())

        return resolved

    @model_validator(mode="after")
    def _normalize_provider_urls(self) -> "ModelConfig":
        self.endpoint_path = _normalize_endpoint_path(self.endpoint_path, default=DEFAULT_CHAT_ENDPOINT_PATH)
        self.embedding_endpoint_path = _normalize_endpoint_path(self.embedding_endpoint_path, default=DEFAULT_EMBEDDING_ENDPOINT_PATH)
        self.speech_endpoint_path = _normalize_endpoint_path(self.speech_endpoint_path, default=DEFAULT_SPEECH_ENDPOINT_PATH)
        self.base_url = _normalize_provider_base_url(self.base_url, endpoint_path=self.endpoint_path)
        if self.embedding_api_key is None:
            self.embedding_api_key = self.api_key
        if self.embedding_base_url is None:
            self.embedding_base_url = self.base_url
        self.embedding_base_url = _normalize_provider_base_url(self.embedding_base_url, endpoint_path=self.embedding_endpoint_path)
        self.speech_base_url = _normalize_provider_base_url(self.speech_base_url, endpoint_path=self.speech_endpoint_path)
        self.video_base_url = _normalize_provider_base_url(self.video_base_url, endpoint_path=self.endpoint_path)
        self.image_base_url = self.image_base_url.strip().rstrip("/") if self.image_base_url else None
        self.image_explicit_url = self.image_explicit_url.strip() if self.image_explicit_url else None
        return self

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
    enable_streaming: bool = True
    auto_select_skills: bool = True
    skill_routing: SkillRoutingConfig | None = Field(default_factory=SkillRoutingConfig)
    parser_retry_limit: int = 1
    enable_retrieval: bool = False
    reasoning_strategy: ReasoningStrategyConfig | None = None
    context_policy: ContextPolicy = Field(default_factory=ContextPolicy.default)
    state_policy: StatePolicy = Field(default_factory=StatePolicy)
    coordination_policy: CoordinationPolicy = Field(default_factory=CoordinationPolicy)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    context_selector: ContextSelector | None = None
    route_planner: RoutePlanner | None = None
    memory_evaluator: MemoryEvaluator | None = None
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
        if "rag_strategy" in normalized and normalized["rag_strategy"] is not None:
            normalized["rag_strategy"] = RagStrategyConfig.from_any(normalized["rag_strategy"])
        if "reasoning_strategy" in normalized and normalized["reasoning_strategy"] is not None:
            normalized["reasoning_strategy"] = ReasoningStrategyConfig.from_any(normalized["reasoning_strategy"])
        if "skill_routing" in normalized and normalized["skill_routing"] is not None:
            normalized["skill_routing"] = SkillRoutingConfig.from_any(normalized["skill_routing"])
        if "context_policy" in normalized and normalized["context_policy"] is not None:
            normalized["context_policy"] = ContextPolicy.from_any(normalized["context_policy"])
        if "state_policy" in normalized and normalized["state_policy"] is not None:
            normalized["state_policy"] = StatePolicy.from_any(normalized["state_policy"])
        if "coordination_policy" in normalized and normalized["coordination_policy"] is not None:
            normalized["coordination_policy"] = CoordinationPolicy.from_any(normalized["coordination_policy"])
        if "memory_policy" in normalized and normalized["memory_policy"] is not None:
            normalized["memory_policy"] = MemoryPolicy.from_any(normalized["memory_policy"])
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
        context_policy: ContextPolicy | dict[str, object] | None = None,
        state_policy: StatePolicy | dict[str, object] | None = None,
        coordination_policy: CoordinationPolicy | dict[str, object] | None = None,
        memory_policy: MemoryPolicy | dict[str, object] | None = None,
        observability: ObservabilityConfig | dict[str, object] | None = None,
        prompt_template: ChatPromptTemplate | None = None,
        skill_routing: SkillRoutingConfig | str | dict[str, object] | None = None,
        default_knowledge_scope: list[str] | None = None,
        **kwargs: object,
    ) -> "RuntimeConfig":
        rag_strategy = RagStrategyConfig.from_any(rag) if rag is not None else None
        payload: dict[str, object] = {
            "system_prompt": system_prompt or cls().system_prompt,
            "prompt_template": prompt_template,
            "rag_strategy": rag_strategy,
            "enable_retrieval": rag_strategy is not None and rag_strategy.mode != "off",
            "reasoning_strategy": ReasoningStrategyConfig.from_any(reasoning) if reasoning is not None else None,
            "default_knowledge_scope": list(default_knowledge_scope or []),
            **kwargs,
        }
        if skill_routing is not None:
            payload["skill_routing"] = SkillRoutingConfig.from_any(skill_routing)
        if context_policy is not None:
            payload["context_policy"] = ContextPolicy.from_any(context_policy)
        if state_policy is not None:
            payload["state_policy"] = StatePolicy.from_any(state_policy)
        if coordination_policy is not None:
            payload["coordination_policy"] = CoordinationPolicy.from_any(coordination_policy)
        if memory_policy is not None:
            payload["memory_policy"] = MemoryPolicy.from_any(memory_policy)
        if observability is not None:
            payload["observability"] = ObservabilityConfig.from_any(observability)
        return cls(**payload)

    @classmethod
    def workflow(
        cls,
        *,
        rag: RagStrategyConfig | str | dict[str, object] | None = None,
        reasoning: ReasoningStrategyConfig | str | dict[str, object] | None = None,
        context_policy: ContextPolicy | dict[str, object] | None = None,
        state_policy: StatePolicy | dict[str, object] | None = None,
        coordination_policy: CoordinationPolicy | dict[str, object] | None = None,
        memory_policy: MemoryPolicy | dict[str, object] | None = None,
        observability: ObservabilityConfig | dict[str, object] | None = None,
        skill_routing: SkillRoutingConfig | str | dict[str, object] | None = None,
        **kwargs: object,
    ) -> "RuntimeConfig":
        base = cls.agent(
            rag=rag,
            reasoning=reasoning,
            context_policy=context_policy,
            state_policy=state_policy,
            coordination_policy=coordination_policy,
            memory_policy=memory_policy,
            observability=observability,
            skill_routing=skill_routing,
            **kwargs,
        )
        return base.model_copy(update={"retrieval_mode": RetrievalMode.EXPLICIT_STEP})
