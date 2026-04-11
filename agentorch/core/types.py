from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    messages: list[Message]
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    message: Message | None = None
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: UsageInfo = Field(default_factory=UsageInfo)
    raw: Any | None = None


class StreamChunk(BaseModel):
    delta_text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    raw: Any | None = None


class ActionType(str, Enum):
    RESPOND = "respond"
    CALL_TOOL = "call_tool"
    SELECT_SKILL = "select_skill"
    ROUTE = "route"
    FINISH = "finish"
    DELEGATE_AGENT = "delegate_agent"
    AGGREGATE = "aggregate"
    RETRIEVE = "retrieve"
    REQUEST_APPROVAL = "request_approval"
    CHECKPOINT = "checkpoint"


class Decision(BaseModel):
    action: ActionType
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    selected_skills: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    selected_scopes: list[str] = Field(default_factory=list)
    route: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionRequest(BaseModel):
    tool_call: ToolCall
    request_id: str
    run_id: str
    thread_id: str | None = None


class ToolExecutionResult(BaseModel):
    tool_call_id: str
    tool_name: str
    output: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False
    error_message: str | None = None
    duration: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptContext(BaseModel):
    system_prompt: str = ""
    user_input: str
    memory_summary: str | None = None
    retrieval_context: str | None = None
    collective_memory_context: str | None = None
    retrieved_evidence: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_report: dict[str, Any] | None = None
    retrieval_coverage: dict[str, Any] | None = None
    collective_memory_evidence: list[dict[str, Any]] = Field(default_factory=list)
    collective_memory_citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_plan: dict[str, Any] | None = None
    knowledge_scope: list[str] = Field(default_factory=list)
    tool_descriptions: list[dict[str, Any]] = Field(default_factory=list)
    skill_instructions: list[str] = Field(default_factory=list)
    output_instruction: str | None = None
    task_packet: dict[str, Any] | None = None
    agent_role: str | None = None
    delegation_context: dict[str, Any] = Field(default_factory=dict)
    conversation: list[Message] = Field(default_factory=list)
    prompt_variables: dict[str, Any] = Field(default_factory=dict)


class ContextSegment(BaseModel):
    segment_id: str
    segment_type: str
    source: str
    content: Any
    display_content: str = ""
    char_count: int = 0
    agent_scope: str | None = None
    thread_scope: str | None = None
    recency: float = 0.0
    reliability: float = 0.0
    task_relevance: float = 0.0
    delegation_depth: int = 0
    novelty: float = 0.0
    redundancy_group: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentScore(BaseModel):
    segment_id: str
    rule_score: float
    rerank_adjustment: float = 0.0
    redundancy_penalty: float = 0.0
    salience_score: float = 0.0
    keep_reason: str = ""
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompactionDecision(BaseModel):
    segment_id: str
    selected: bool
    selected_representation: str | None = None
    selected_char_count: int = 0
    reason: str = ""
    inhibition_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SalienceReport(BaseModel):
    mode: str
    attention_profile: dict[str, float] = Field(default_factory=dict)
    selected_segments: list[ContextSegment] = Field(default_factory=list)
    dropped_segments: list[ContextSegment] = Field(default_factory=list)
    segment_scores: list[SegmentScore] = Field(default_factory=list)
    decisions: list[CompactionDecision] = Field(default_factory=list)
    inhibition_events: list[dict[str, Any]] = Field(default_factory=list)
    compression_reason: str | None = None
    estimated_total_chars_before: int = 0
    estimated_total_chars_after: int = 0


class ContextEnvelope(BaseModel):
    request_id: str
    run_id: str
    thread_id: str
    trace_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    request_id: str
    run_id: str
    thread_id: str
    output_text: str
    messages: list[Message] = Field(default_factory=list)
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    usage: UsageInfo = Field(default_factory=UsageInfo)
    finish_reason: str | None = None
    status: Literal["completed", "failed", "waiting_human"] = "completed"
    error_message: str | None = None
    feedback_id: str | None = None
    await_reason: str | None = None
    requires_response: bool = False
    response_schema: dict[str, Any] | None = None
    reasoning: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: str = ""
    reasoning_kind: str | None = None
    reasoning_metadata: dict[str, Any] = Field(default_factory=dict)


class RunStreamEvent(BaseModel):
    event_type: str
    request_id: str
    run_id: str
    thread_id: str
    agent_name: str | None = None
    task_id: str | None = None
    parent_task_id: str | None = None
    delta_text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: RunResult | None = None
