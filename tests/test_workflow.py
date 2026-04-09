import asyncio

from agentorch.workflow import Context, Edge, Node, Workflow, WorkflowRunner


def test_workflow_condition_routing():
    asyncio.run(_test_workflow_condition_routing())


async def _test_workflow_condition_routing():
    async def router_handler(node, context):
        return {"status": "completed", "route": "yes"}

    async def tool_handler(node, context):
        return {"status": "completed", "value": 1}

    workflow = Workflow(
        entry_node="r1",
        nodes=[
            Node(id="r1", kind="router"),
            Node(id="t1", kind="tool"),
        ],
        edges=[Edge(source="r1", target="t1", kind="condition", condition="yes")],
    )
    runner = WorkflowRunner({"router": router_handler, "tool": tool_handler})
    result = await runner.run(workflow, Context(thread_id="t", user_input="hi"))
    assert result["value"] == 1
