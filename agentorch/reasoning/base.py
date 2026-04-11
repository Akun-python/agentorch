from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from agentorch.agents import AgentResult, TaskPacket
from agentorch.core import ContextEnvelope, Decision, Message, ModelResponse, ToolExecutionResult, UsageInfo
from agentorch.knowledge import RetrievalPlan, RetrievedEvidence


class BasePolicy(ABC):
    @abstractmethod
    async def decide(self, response: ModelResponse) -> Decision:
        raise NotImplementedError


class DelegationPolicy(ABC):
    @abstractmethod
    async def build_task(self, *, goal: str, context: dict[str, object]) -> TaskPacket:
        raise NotImplementedError


class RetrievalPolicy(ABC):
    @abstractmethod
    async def plan(self, *, user_input: str, available_scopes: list[str]) -> RetrievalPlan:
        raise NotImplementedError


class AggregationPolicy(ABC):
    @abstractmethod
    async def aggregate(self, *, results: list[AgentResult]) -> dict[str, object]:
        raise NotImplementedError


class ReflectionPolicy(ABC):
    @abstractmethod
    async def reflect(self, *, output_text: str, evidence: list[RetrievedEvidence]) -> dict[str, object]:
        raise NotImplementedError


class ReasoningKind(str, Enum):
    COT = "cot"
    REACT = "react"
    PLAN_EXECUTE = "plan_execute"
    TOT = "tot"
    REFLEXION = "reflexion"


class ReasoningStrategyConfig(BaseModel):
    kind: ReasoningKind = ReasoningKind.REACT
    config: dict[str, Any] = Field(default_factory=dict)
    allow_tool_calls: bool = True
    allow_retrieval: bool = True
    allow_delegation: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_shortcuts(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"kind": data}
        return data

    @classmethod
    def from_any(
        cls,
        value: "ReasoningStrategyConfig | ReasoningKind | str | dict[str, Any] | None",
        **overrides: Any,
    ) -> "ReasoningStrategyConfig":
        if value is None:
            base = cls()
        elif isinstance(value, cls):
            base = value.model_copy(deep=True)
        elif isinstance(value, (ReasoningKind, str)):
            base = cls(kind=value)
        else:
            base = cls.model_validate(value)
        if overrides:
            return base.model_copy(update=overrides)
        return base

    @classmethod
    def react(cls, **kwargs: Any) -> "ReasoningStrategyConfig":
        return cls(kind=ReasoningKind.REACT, **kwargs)

    @classmethod
    def cot(cls, **kwargs: Any) -> "ReasoningStrategyConfig":
        return cls(kind=ReasoningKind.COT, allow_tool_calls=False, **kwargs)

    @classmethod
    def plan_execute(cls, **kwargs: Any) -> "ReasoningStrategyConfig":
        return cls(kind=ReasoningKind.PLAN_EXECUTE, allow_tool_calls=True, allow_retrieval=True, **kwargs)

    @classmethod
    def tot(cls, **kwargs: Any) -> "ReasoningStrategyConfig":
        return cls(kind=ReasoningKind.TOT, allow_tool_calls=True, allow_retrieval=True, **kwargs)

    @classmethod
    def reflexion(cls, **kwargs: Any) -> "ReasoningStrategyConfig":
        return cls(kind=ReasoningKind.REFLEXION, allow_tool_calls=True, allow_retrieval=True, **kwargs)


class ReasoningConfig(BaseModel):
    kind: ReasoningKind
    max_steps: int = 8
    expose_trace: bool = True


class CotConfig(ReasoningConfig):
    kind: ReasoningKind = ReasoningKind.COT
    allow_tool_calls: bool = False


class ReactConfig(ReasoningConfig):
    kind: ReasoningKind = ReasoningKind.REACT


class PlanExecuteConfig(ReasoningConfig):
    kind: ReasoningKind = ReasoningKind.PLAN_EXECUTE
    max_planning_steps: int = 5
    max_execution_steps: int = 8
    allow_replan: bool = True


class TotConfig(ReasoningConfig):
    kind: ReasoningKind = ReasoningKind.TOT
    branch_factor: int = 3
    max_depth: int = 3
    top_k: int = 2


class ReflexionConfig(ReasoningConfig):
    kind: ReasoningKind = ReasoningKind.REFLEXION
    max_attempts: int = 3
    enable_self_reflection: bool = True


class ReasoningStep(BaseModel):
    index: int
    kind: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningTrace(BaseModel):
    steps: list[ReasoningStep] = Field(default_factory=list)

    @property
    def trace_text(self) -> str:
        return "\n".join(f"[{step.index}] {step.kind}: {step.content}" for step in self.steps)


class ReasoningResult(BaseModel):
    final_output: str
    steps: list[ReasoningStep] = Field(default_factory=list)
    trace_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningSession(BaseModel):
    kind: ReasoningKind
    user_input: str
    thread_id: str
    trace: ReasoningTrace = Field(default_factory=ReasoningTrace)
    state: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningSessionContext(BaseModel):
    user_input: str
    thread_id: str
    envelope: ContextEnvelope
    conversation: list[Message] = Field(default_factory=list)
    memory_summary: str | None = None
    retrieval_payload: dict[str, Any] = Field(default_factory=dict)
    task_packet: dict[str, Any] | None = None
    delegation_context: dict[str, Any] = Field(default_factory=dict)
    agent_role: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    usage: UsageInfo = Field(default_factory=UsageInfo)
    messages: list[Message] = Field(default_factory=list)
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    stream_enabled: bool = False
    stream_writer: Any | None = None


class BaseReasoningFramework(ABC):
    config: ReasoningConfig

    def __init__(self, config: ReasoningConfig) -> None:
        self.config = config

    def initialize(self, context: ReasoningSessionContext) -> ReasoningSession:
        return ReasoningSession(kind=self.config.kind, user_input=context.user_input, thread_id=context.thread_id)

    async def next_action(
        self,
        session: ReasoningSession,
        model_response: ModelResponse | None = None,
        observation: dict[str, Any] | None = None,
    ) -> Decision:
        raise NotImplementedError

    def finalize(self, session: ReasoningSession) -> ReasoningResult:
        final_output = str(session.state.get("final_output", ""))
        return ReasoningResult(
            final_output=final_output,
            steps=session.trace.steps,
            trace_text=session.trace.trace_text,
            metadata=session.metadata,
        )

    @abstractmethod
    async def execute(self, runtime: Any, context: ReasoningSessionContext) -> ReasoningResult:
        raise NotImplementedError
