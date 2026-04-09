from agentorch.core import Message, PromptContext
from agentorch.prompts import PromptBuilder


def test_prompt_builder_does_not_duplicate_user_when_conversation_exists():
    builder = PromptBuilder()
    messages = builder.build_messages(
        PromptContext(
            system_prompt="system",
            user_input="hello",
            conversation=[
                Message(role="user", content="hello"),
                Message(role="assistant", content="", tool_calls=[]),
                Message(role="tool", content='{"sum": 579}', tool_call_id="call-1"),
            ],
        )
    )
    assert len(messages) == 4
    assert [message.role for message in messages] == ["system", "user", "assistant", "tool"]


def test_prompt_builder_includes_retrieval_and_task_context():
    builder = PromptBuilder()
    messages = builder.build_messages(
        PromptContext(
            system_prompt="system",
            user_input="hello",
            retrieval_context="knowledge chunk",
            task_packet={"goal": "solve"},
            agent_role="planner",
            delegation_context={"from_agent": "supervisor"},
        )
    )
    assert "Retrieved Knowledge" in messages[0].content
    assert "knowledge chunk" in messages[0].content
    assert "Task Packet" in messages[0].content
