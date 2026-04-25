from __future__ import annotations

from .bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from agentorch.agents.registry import AgentRegistry
from agentorch.agents.supervisor import AgentRouteDecision, SupervisorPolicy
from agentorch.agents.types import TaskPacket


class HarnessSupervisorPolicy(SupervisorPolicy):
    _PHASE_TO_AGENT = {
        "plan": "planner",
        "execute": "codex_operator",
        "review": "reviewer",
        "integrate": "integrator",
    }

    async def select_agents(self, task: TaskPacket, registry: AgentRegistry) -> AgentRouteDecision:
        phase = str(task.metadata.get("phase", "execute")).lower()
        preferred = self._PHASE_TO_AGENT.get(phase)
        selected: list[str] = []
        if preferred:
            for spec in registry.list_specs():
                if spec.name == preferred:
                    selected.append(preferred)
                    break
        if not selected and registry.list_specs():
            selected.append(registry.list_specs()[0].name)
        return AgentRouteDecision(selected_agents=selected, reason=f"phase_route:{phase}")
