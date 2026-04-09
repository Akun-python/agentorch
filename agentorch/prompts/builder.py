from __future__ import annotations

from jinja2 import Template

from agentorch.core import Message, PromptContext


class PromptTemplate:
    def __init__(self, template: str) -> None:
        self.template = Template(template)

    def render(self, **kwargs: object) -> str:
        return self.template.render(**kwargs)


class PromptBuilder:
    def __init__(self, system_template: PromptTemplate | None = None) -> None:
        self.system_template = system_template or PromptTemplate(
            "{{ system_prompt }}\n"
            "{% if memory_summary %}\nMemory Summary:\n{{ memory_summary }}\n{% endif %}"
            "{% if retrieval_context %}\nRetrieved Knowledge:\n{{ retrieval_context }}\n{% endif %}"
            "{% if agent_role %}\nAgent Role:\n{{ agent_role }}\n{% endif %}"
            "{% if task_packet %}\nTask Packet:\n{{ task_packet }}\n{% endif %}"
            "{% if delegation_context %}\nDelegation Context:\n{{ delegation_context }}\n{% endif %}"
            "{% if skill_instructions %}\nSkill Instructions:\n{{ skill_instructions|join('\\n\\n') }}\n{% endif %}"
            "{% if tool_descriptions %}\nAvailable Tools:\n{{ tool_descriptions }}\n{% endif %}"
            "{% if output_instruction %}\nOutput Constraint:\n{{ output_instruction }}\n{% endif %}"
        )

    def build_messages(self, context: PromptContext) -> list[Message]:
        system_text = self.system_template.render(
            system_prompt=context.system_prompt,
            memory_summary=context.memory_summary or "",
            retrieval_context=context.retrieval_context or "",
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
