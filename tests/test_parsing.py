import asyncio

from pydantic import BaseModel

from agentorch import Agent, JSONParser, KeyValueParser, ListParser, PydanticParser, Runtime, parser_chain
from agentorch.core import Message, ModelRequest, ModelResponse, UsageInfo
from agentorch.models.base import BaseModelAdapter


class UserProfile(BaseModel):
    name: str
    age: int


class StructuredModel(BaseModelAdapter):
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            message=Message(role="assistant", content=self.content),
            content=self.content,
            finish_reason="stop",
            usage=UsageInfo(total_tokens=8),
        )


def test_json_parser_extracts_json_from_code_block():
    payload = "Here is the result:\n```json\n{\"name\": \"agentorch\", \"stars\": 3}\n```"
    parsed = asyncio.run(JSONParser().parse(payload))
    assert parsed == {"name": "agentorch", "stars": 3}


def test_list_parser_supports_markdown_bullets():
    payload = "- plan\n- execute\n- verify"
    parsed = asyncio.run(ListParser().parse(payload))
    assert parsed == ["plan", "execute", "verify"]


def test_key_value_parser_supports_plain_lines():
    payload = "name: agentorch\nversion: 0.1.0"
    parsed = asyncio.run(KeyValueParser().parse(payload))
    assert parsed == {"name": "agentorch", "version": "0.1.0"}


def test_pydantic_parser_repairs_json_code_block():
    payload = "```json\n{\"name\": \"sun\", \"age\": 2}\n```"
    parsed = asyncio.run(PydanticParser(UserProfile).parse(payload))
    assert parsed.name == "sun"
    assert parsed.age == 2


def test_fallback_parser_can_compose_multiple_formats():
    parser = parser_chain(JSONParser(), KeyValueParser())
    payload = "name: agentorch\nkind: framework"
    parsed = asyncio.run(parser.parse(payload))
    assert parsed == {"name": "agentorch", "kind": "framework"}


def test_agent_run_parsed_returns_structured_output_and_injects_format_prompt():
    asyncio.run(_test_agent_run_parsed_returns_structured_output_and_injects_format_prompt())


async def _test_agent_run_parsed_returns_structured_output_and_injects_format_prompt():
    model = StructuredModel('{"name": "agentorch", "age": 1}')
    agent = Agent(runtime=Runtime(model=model))
    result = await agent.run_parsed(
        "Generate a user profile.",
        thread_id="parsed-1",
        parser=PydanticParser(UserProfile),
    )
    assert result.parsed.name == "agentorch"
    assert result.parsed.age == 1
    first_request = model.requests[0]
    user_messages = [message for message in first_request.messages if message.role == "user"]
    assert user_messages
    assert "Output format" in user_messages[-1].content
    assert "Return a valid JSON object" in user_messages[-1].content
