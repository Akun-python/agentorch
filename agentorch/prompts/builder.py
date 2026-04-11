from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import Template

from agentorch.core import Message, PromptContext
from .cards import ChatPromptTemplate


class PromptTemplate:
    def __init__(self, template: str) -> None:
        self.template = Template(template)

    def render(self, **kwargs: object) -> str:
        return self.template.render(**kwargs)


@dataclass
class ReasoningPromptProfile:
    kind: str
    instruction: str


class PromptBuilder:
    def __init__(self, system_template: PromptTemplate | None = None, *, chat_template: ChatPromptTemplate | None = None) -> None:
        self.chat_template = chat_template
        self.system_template = system_template or PromptTemplate(
            "{{ system_prompt }}\n"
            "{% if memory_summary %}\nMemory Summary:\n{{ memory_summary }}\n{% endif %}"
            "{% if retrieval_context %}\nRetrieved Knowledge:\n{{ retrieval_context }}\n{% endif %}"
            "{% if collective_memory_context %}\nCollective Memory:\n{{ collective_memory_context }}\n{% endif %}"
            "{% if retrieved_evidence %}\nRetrieved Evidence:\n{{ retrieved_evidence }}\n{% endif %}"
            "{% if citations %}\nCitations:\n{{ citations }}\n{% endif %}"
            "{% if retrieval_report %}\nRetrieval Report:\n{{ retrieval_report }}\n{% endif %}"
            "{% if retrieval_coverage %}\nRetrieval Coverage:\n{{ retrieval_coverage }}\n{% endif %}"
            "{% if collective_memory_evidence %}\nCollective Memory Evidence:\n{{ collective_memory_evidence }}\n{% endif %}"
            "{% if collective_memory_citations %}\nCollective Memory Citations:\n{{ collective_memory_citations }}\n{% endif %}"
            "{% if retrieval_plan %}\nRetrieval Plan:\n{{ retrieval_plan }}\n{% endif %}"
            "{% if knowledge_scope %}\nKnowledge Scope:\n{{ knowledge_scope }}\n{% endif %}"
            "{% if agent_role %}\nAgent Role:\n{{ agent_role }}\n{% endif %}"
            "{% if task_packet %}\nTask Packet:\n{{ task_packet }}\n{% endif %}"
            "{% if delegation_context %}\nDelegation Context:\n{{ delegation_context }}\n{% endif %}"
            "{% if skill_instructions %}\nSkill Instructions:\n{{ skill_instructions|join('\\n\\n') }}\n{% endif %}"
            "{% if tool_descriptions %}\nAvailable Tools:\n{{ tool_descriptions }}\n{% endif %}"
            "{% if output_instruction %}\nOutput Constraint:\n{{ output_instruction }}\n{% endif %}"
        )

    def _template_variables(self, context: PromptContext) -> dict[str, Any]:
        return {
            **context.model_dump(),
            **context.prompt_variables,
            "conversation": context.conversation,
        }

    def build_messages(self, context: PromptContext) -> list[Message]:
        if self.chat_template is not None:
            messages = self.chat_template.format_messages(**self._template_variables(context))
            if not any(message.role == "user" for message in messages):
                messages.append(Message(role="user", content=context.user_input))
            return messages
        system_text = self.system_template.render(
            system_prompt=context.system_prompt,
            memory_summary=context.memory_summary or "",
            retrieval_context=context.retrieval_context or "",
            collective_memory_context=context.collective_memory_context or "",
            retrieved_evidence=context.retrieved_evidence,
            citations=context.citations,
            retrieval_report=context.retrieval_report or {},
            retrieval_coverage=context.retrieval_coverage or {},
            collective_memory_evidence=context.collective_memory_evidence,
            collective_memory_citations=context.collective_memory_citations,
            retrieval_plan=context.retrieval_plan or {},
            knowledge_scope=context.knowledge_scope,
            task_packet=context.task_packet or {},
            agent_role=context.agent_role or "",
            delegation_context=context.delegation_context or {},
            skill_instructions=context.skill_instructions,
            tool_descriptions=context.tool_descriptions,
            output_instruction=context.output_instruction or "",
        ).strip()
        messages = [Message(role="system", content=system_text)]
        messages.extend(context.conversation)
        # The runtime usually appends the current user input into conversation
        # before prompt construction. Only inject a fallback user message when
        # the conversation is truly empty.
        if not context.conversation:
            messages.append(Message(role="user", content=context.user_input))
        return messages

    def build_reasoning_messages(self, context: PromptContext, profile: ReasoningPromptProfile) -> list[Message]:
        enriched = context.model_copy(
            update={
                "output_instruction": "\n".join(
                    value for value in [context.output_instruction or "", profile.instruction] if value
                )
            }
        )
        return self.build_messages(enriched)
