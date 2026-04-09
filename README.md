# agentorch

`agentorch` is a code-first, async-first Python agent orchestration library.

It provides:

- A normalized OpenAI-compatible model interface
- Structured tool definitions and execution
- Skill package loading
- Thread memory, long-term records, and checkpoints
- Python-defined workflows
- Runtime orchestration with prompt building and reasoning policies
- Local sandbox execution for higher-risk tools
- Structured observability primitives

## Quick Start

```python
from pydantic import BaseModel

from agentorch import Agent, OpenAIModel, Runtime, ToolRegistry, tool


class AddInput(BaseModel):
    a: int
    b: int


@tool(description="Add two integers together.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}


model = OpenAIModel(model="gpt-4.1-mini", api_key="your-api-key")
tools = ToolRegistry()
tools.register(add_numbers)
runtime = Runtime(model=model, tools=tools)
agent = Agent(runtime=runtime)

result = agent.run_sync("Use the add_numbers tool to add 2 and 3.", thread_id="demo-thread")
print(result.output_text)
```
