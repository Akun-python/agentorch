from agentorch.agents import AgentCapability, AgentRegistry, AgentSpec


def test_agent_registry_register_and_find():
    registry = AgentRegistry()
    agent = object()
    registry.register(
        AgentSpec(
            name="planner",
            description="Planning specialist",
            tags=["plan", "workflow"],
            capabilities=[AgentCapability.PLAN],
            allowed_knowledge_scopes=["architecture"],
        ),
        agent,
    )
    assert registry.get("planner").agent is agent
    assert registry.find_by_tags(["workflow"])[0].spec.name == "planner"
    assert registry.find_by_capabilities([AgentCapability.PLAN])[0].spec.name == "planner"
    assert registry.find_by_knowledge_scope(["architecture"])[0].spec.name == "planner"
