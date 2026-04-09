from agentorch.core import Message, ToolCall
from agentorch.models import OpenAIModel


def test_openai_message_conversion_includes_tool_calls():
    model = OpenAIModel(model="gpt-4.1", api_key="test-key", base_url="https://api.openai.com/v1")
    message = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})],
    )
    payload = model._message_to_openai(message)
    assert payload["role"] == "assistant"
    assert payload["content"] is None
    assert payload["tool_calls"][0]["id"] == "call-1"
    assert payload["tool_calls"][0]["function"]["name"] == "lookup"
