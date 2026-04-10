from __future__ import annotations

from typing import Any, Literal

from jinja2 import Template
from pydantic import BaseModel, Field

from agentorch.core import Message


class TextPromptCard(BaseModel):
    kind: Literal["text"] = "text"
    role: Literal["system", "user", "assistant", "tool"]
    template: str
    name: str | None = None

    def render(self, variables: dict[str, Any]) -> Message:
        return Message(
            role=self.role,
            content=Template(self.template).render(**variables).strip(),
            name=self.name,
        )


class MessagesPlaceholderCard(BaseModel):
    kind: Literal["messages_placeholder"] = "messages_placeholder"
    variable_name: str
    optional: bool = True

    def render(self, variables: dict[str, Any]) -> list[Message]:
        value = variables.get(self.variable_name, [])
        if not value and self.optional:
            return []
        return [item if isinstance(item, Message) else Message.model_validate(item) for item in value]


class FewShotExample(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    user: str
    assistant: str
    system: str | None = None


class FewShotPromptCard(BaseModel):
    kind: Literal["few_shot"] = "few_shot"
    examples: list[FewShotExample] = Field(default_factory=list)
    include_system_examples: bool = False

    def render(self, variables: dict[str, Any]) -> list[Message]:
        rendered: list[Message] = []
        for example in self.examples:
            local_vars = {**variables, **example.input}
            if self.include_system_examples and example.system:
                rendered.append(Message(role="system", content=Template(example.system).render(**local_vars).strip()))
            rendered.append(Message(role="user", content=Template(example.user).render(**local_vars).strip()))
            rendered.append(Message(role="assistant", content=Template(example.assistant).render(**local_vars).strip()))
        return rendered


PromptCard = TextPromptCard | MessagesPlaceholderCard | FewShotPromptCard


class ChatPromptTemplate(BaseModel):
    cards: list[PromptCard] = Field(default_factory=list)
    partial_variables: dict[str, Any] = Field(default_factory=dict)

    def partial(self, **kwargs: Any) -> "ChatPromptTemplate":
        return self.model_copy(update={"partial_variables": {**self.partial_variables, **kwargs}})

    def format_messages(self, **variables: Any) -> list[Message]:
        merged = {**self.partial_variables, **variables}
        messages: list[Message] = []
        for card in self.cards:
            if isinstance(card, TextPromptCard):
                messages.append(card.render(merged))
            elif isinstance(card, MessagesPlaceholderCard):
                messages.extend(card.render(merged))
            elif isinstance(card, FewShotPromptCard):
                messages.extend(card.render(merged))
        return messages
