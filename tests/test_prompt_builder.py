from agentorch.core import Message, PromptContext
from agentorch.prompts import ChatPromptTemplate, FewShotExample, FewShotPromptCard, MessagesPlaceholderCard, PromptBuilder, TextPromptCard


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
            collective_memory_context="shared migration route",
            retrieved_evidence=[{"summary": "chunk summary"}],
            citations=[{"document_id": "doc-1"}],
            collective_memory_evidence=[{"kind": "route", "content": "shared migration route"}],
            collective_memory_citations=[{"record_id": 1}],
            retrieval_plan={"strategy": "inline"},
            knowledge_scope=["engineering"],
            task_packet={"goal": "solve"},
            agent_role="planner",
            delegation_context={"from_agent": "supervisor"},
        )
    )
    assert "Retrieved Knowledge" in messages[0].content
    assert "knowledge chunk" in messages[0].content
    assert "Collective Memory" in messages[0].content
    assert "shared migration route" in messages[0].content
    assert "Retrieved Evidence" in messages[0].content
    assert "Citations" in messages[0].content
    assert "Collective Memory Evidence" in messages[0].content
    assert "Collective Memory Citations" in messages[0].content
    assert "Knowledge Scope" in messages[0].content
    assert "Task Packet" in messages[0].content


def test_prompt_builder_supports_chat_prompt_cards_and_placeholders():
    builder = PromptBuilder(
        chat_template=ChatPromptTemplate(
            cards=[
                TextPromptCard(role="system", template="You are {{ agent_role }}."),
                FewShotPromptCard(
                    examples=[FewShotExample(input={"topic": "math"}, user="Solve {{ topic }}", assistant="Use step-by-step reasoning.")],
                ),
                MessagesPlaceholderCard(variable_name="conversation"),
                TextPromptCard(role="user", template="Question: {{ user_input }}"),
            ]
        )
    )
    messages = builder.build_messages(
        PromptContext(
            system_prompt="ignored",
            user_input="What is 2+2?",
            agent_role="planner",
            conversation=[Message(role="assistant", content="Previous context")],
        )
    )
    assert messages[0].role == "system"
    assert messages[0].content == "You are planner."
    assert any(message.content == "Solve math" for message in messages)
    assert any(message.content == "Use step-by-step reasoning." for message in messages)
    assert messages[-1].content == "Question: What is 2+2?"


def test_chat_prompt_template_partial_merges_variables():
    template = ChatPromptTemplate(
        cards=[
            TextPromptCard(role="system", template="Role={{ agent_role }}"),
            TextPromptCard(role="user", template="Question={{ user_input }}"),
        ]
    ).partial(agent_role="planner")

    messages = template.format_messages(user_input="Where is the evidence?")

    assert messages[0].content == "Role=planner"
    assert messages[1].content == "Question=Where is the evidence?"
