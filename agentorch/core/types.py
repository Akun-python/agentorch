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


class Decision(BaseModel):
    action: ActionType
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    selected_skills: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
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
    tool_descriptions: list[dict[str, Any]] = Field(default_factory=list)
    skill_instructions: list[str] = Field(default_factory=list)
    output_instruction: str | None = None
    task_packet: dict[str, Any] | None = None
    agent_role: str | None = None
    delegation_context: dict[str, Any] = Field(default_factory=dict)
    conversation: list[Message] = Field(default_factory=list)


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
    status: Literal["completed", "failed"] = "completed"
    error_message: str | None = None
