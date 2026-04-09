# LangGraph Python 参考文档

生成时间：2026-03-30
来源范围：`https://docs.langchain.com/oss/python/langgraph/`

## 文档说明

- 这份文档按官方 LangGraph Python 文档树整理，共覆盖 31 个页面。
- 每个页面都给出：页面定位、官方页重点、最小示例代码。
- 示例代码是为学习整理而写的最小示例，不是官方文档逐字复制。

## 通用安装

```bash
pip install -U langgraph langchain langsmith
export ANTHROPIC_API_KEY="your-api-key"
```

## 通用基础环境

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    message: str


def hello(state: State):
    return {"message": f"hello {state['message']}"}

app = StateGraph(State).add_node("hello", hello).add_edge(START, "hello").add_edge("hello", END).compile()
```

---

## 一、核心页面

### Memory

- 原文页面：https://docs.langchain.com/oss/python/langgraph/add-memory
- 页面定位：该页关注 LangGraph 的长时执行能力，决定图能否暂停、恢复、记忆和回放。
- 官方页重点：
  - Add short-term memory
  - Use in production
  - Use in subgraphs
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    message: str


def echo(state: State):
    return {"message": state["message"]}

app = StateGraph(State).add_node("echo", echo).add_edge(START, "echo").add_edge("echo", END).compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "thread-1"}}
print(app.invoke({"message": "hi"}, config=config))
```

### Build a custom RAG agent with LangGraph

- 原文页面：https://docs.langchain.com/oss/python/langgraph/agentic-rag
- 页面定位：这是官方实践/设计页，重点看状态设计、控制流和节点职责划分。
- 官方页重点：
  - Overview
  - Concepts
  - Setup
  - 1. Preprocess documents
- 最小示例：

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class State(TypedDict):
    question: str
    context: str


def retrieve(state: State):
    return {"context": f"retrieved docs for: {state['question']}"}

app = StateGraph(State).add_node("retrieve", retrieve).add_edge(START, "retrieve").add_edge("retrieve", END).compile()
```

### Application structure

- 原文页面：https://docs.langchain.com/oss/python/langgraph/application-structure
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Key concepts
  - File structure
  - Configuration file
  - Examples
- 最小示例：

```plaintext
my-app/
├── my_agent/
│   ├── agent.py
│   ├── nodes.py
│   └── state.py
├── .env
├── requirements.txt
└── langgraph.json
```

### Case studies

- 原文页面：https://docs.langchain.com/oss/python/langgraph/case-studies
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    message: str


def say_hello(state: State):
    return {"message": f"hello, {state['message']}"}


graph = StateGraph(State)
graph.add_node("say_hello", say_hello)
graph.add_edge(START, "say_hello")
graph.add_edge("say_hello", END)
app = graph.compile()
print(app.invoke({"message": "langgraph"}))
```

### Changelog

- 原文页面：https://docs.langchain.com/oss/python/langgraph/changelog-py
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
import langgraph
print(langgraph.__version__)
```

### Choosing between Graph and Functional APIs

- 原文页面：https://docs.langchain.com/oss/python/langgraph/choosing-apis
- 页面定位：这是 LangGraph API 的核心入口页，重点理解状态、节点、边和执行方式。
- 官方页重点：
  - Quick decision guide
  - Detailed comparison
  - When to use the Graph API
- 最小示例：

```python
from langgraph.graph import StateGraph
from langgraph.func import entrypoint, task
# Graph API 适合显式建模节点/边；Functional API 适合在现有 Python 控制流中接入 LangGraph 能力。
```

### LangSmith Deployment

- 原文页面：https://docs.langchain.com/oss/python/langgraph/deploy
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Prerequisites
  - Deploy your agent
  - 1. Create a repository on GitHub
  - 2. Deploy to LangSmith
- 最小示例：

```json
{
  "graphs": {
    "agent": "./app.py:graph"
  },
  "env": ".env"
}
```

### Durable execution

- 原文页面：https://docs.langchain.com/oss/python/langgraph/durable-execution
- 页面定位：该页关注 LangGraph 的长时执行能力，决定图能否暂停、恢复、记忆和回放。
- 官方页重点：
  - Requirements
  - Determinism and consistent replay
  - Durability modes
  - Using tasks in nodes
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    message: str


def echo(state: State):
    return {"message": state["message"]}

app = StateGraph(State).add_node("echo", echo).add_edge(START, "echo").add_edge("echo", END).compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "thread-1"}}
print(app.invoke({"message": "hi"}, config=config))
```

### Functional API overview

- 原文页面：https://docs.langchain.com/oss/python/langgraph/functional-api
- 页面定位：这是 LangGraph API 的核心入口页，重点理解状态、节点、边和执行方式。
- 官方页重点：
  - Functional API vs. Graph API
  - Example
  - Entrypoint
  - Definition
- 最小示例：

```python
from langgraph.func import entrypoint, task

@task
def make_joke(topic: str) -> str:
    return f"A joke about {topic}"

@entrypoint()
def workflow(topic: str) -> str:
    return make_joke(topic).result()

print(workflow.invoke("ice cream"))
```

### Graph API overview

- 原文页面：https://docs.langchain.com/oss/python/langgraph/graph-api
- 页面定位：这是 LangGraph API 的核心入口页，重点理解状态、节点、边和执行方式。
- 官方页重点：
  - Graphs
  - StateGraph
  - Compiling your graph
  - State
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    topic: str
    joke: str


def write_joke(state: State):
    return {"joke": f"A joke about {state['topic']}"}

builder = StateGraph(State)
builder.add_node("write_joke", write_joke)
builder.add_edge(START, "write_joke")
builder.add_edge("write_joke", END)
app = builder.compile()
```

### Install LangGraph

- 原文页面：https://docs.langchain.com/oss/python/langgraph/install
- 页面定位：适合先建立 LangGraph 的整体认知，再进入具体功能页。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```bash
pip install -U langgraph
# 或 uv add langgraph
```

### Interrupts

- 原文页面：https://docs.langchain.com/oss/python/langgraph/interrupts
- 页面定位：该页关注 LangGraph 的长时执行能力，决定图能否暂停、恢复、记忆和回放。
- 官方页重点：
  - Pause using interrupt
  - Resuming interrupts
  - Common patterns
  - Stream with human-in-the-loop (HITL) interrupts
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    approved: bool


def review(state: State):
    decision = interrupt({"question": "Approve this action?"})
    return {"approved": decision == "yes"}

app = StateGraph(State).add_node("review", review).add_edge(START, "review").add_edge("review", END).compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "review-1"}}
app.invoke({"approved": False}, config=config)
app.invoke(Command(resume="yes"), config=config)
```

### Run a local server

- 原文页面：https://docs.langchain.com/oss/python/langgraph/local-server
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Prerequisites
  - 1. Install the LangGraph CLI
  - 2. Create a LangGraph app
  - 3. Install dependencies
- 最小示例：

```bash
langgraph new my-app --template new-langgraph-project-python
cd my-app
pip install -e .
langgraph dev
```

### LangSmith Observability

- 原文页面：https://docs.langchain.com/oss/python/langgraph/observability
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Prerequisites
  - Enable tracing
  - Trace selectively
- 最小示例：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=langgraph-reference
```

### LangGraph overview

- 原文页面：https://docs.langchain.com/oss/python/langgraph/overview
- 页面定位：适合先建立 LangGraph 的整体认知，再进入具体功能页。
- 官方摘要：Gain control with LangGraph to design agents that reliably handle complex tasks
- 官方页重点：
  - <Icon icon="download" /> Install
  - Core benefits
  - LangGraph ecosystem
  - Acknowledgements
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    message: str


def say_hello(state: State):
    return {"message": f"hello, {state['message']}"}


graph = StateGraph(State)
graph.add_node("say_hello", say_hello)
graph.add_edge(START, "say_hello")
graph.add_edge("say_hello", END)
app = graph.compile()
print(app.invoke({"message": "langgraph"}))
```

### Persistence

- 原文页面：https://docs.langchain.com/oss/python/langgraph/persistence
- 页面定位：该页关注 LangGraph 的长时执行能力，决定图能否暂停、恢复、记忆和回放。
- 官方页重点：
  - Why use persistence
  - Core concepts
  - Threads
  - Checkpoints
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    message: str


def echo(state: State):
    return {"message": state["message"]}

app = StateGraph(State).add_node("echo", echo).add_edge(START, "echo").add_edge("echo", END).compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "thread-1"}}
print(app.invoke({"message": "hi"}, config=config))
```

### LangGraph runtime

- 原文页面：https://docs.langchain.com/oss/python/langgraph/pregel
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Overview
  - Actors
  - Channels
  - Examples
- 最小示例：

```python
from langgraph.graph import StateGraph
# 编译后的 StateGraph / entrypoint 本质上都会得到可 invoke/stream 的 Pregel runtime 实例。
```

### Quickstart

- 原文页面：https://docs.langchain.com/oss/python/langgraph/quickstart
- 页面定位：适合先建立 LangGraph 的整体认知，再进入具体功能页。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

model = init_chat_model("claude-sonnet-4-6", temperature=0)

@tool
def add(a: int, b: int) -> int:
    return a + b

agent = create_react_agent(model, tools=[add])
print(agent.invoke({"messages": [{"role": "user", "content": "2+3 等于多少？"}]}))
```

### Build a custom SQL agent

- 原文页面：https://docs.langchain.com/oss/python/langgraph/sql-agent
- 页面定位：这是官方实践/设计页，重点看状态设计、控制流和节点职责划分。
- 官方页重点：
  - Concepts
  - Setup
  - Installation
  - LangSmith
- 最小示例：

```python
import sqlite3
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

conn = sqlite3.connect(":memory:")
conn.execute("create table sales (product text, amount int)")

class State(TypedDict):
    query: str
    result: str


def run_query(state: State):
    rows = conn.execute(state["query"]).fetchall()
    return {"result": str(rows)}

app = StateGraph(State).add_node("run_query", run_query).add_edge(START, "run_query").add_edge("run_query", END).compile()
```

### Streaming

- 原文页面：https://docs.langchain.com/oss/python/langgraph/streaming
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Get started
  - Basic usage
  - Stream output format (v2)
  - Stream modes
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    message: str


def say_hello(state: State):
    return {"message": f"hello, {state['message']}"}


graph = StateGraph(State)
graph.add_node("say_hello", say_hello)
graph.add_edge(START, "say_hello")
graph.add_edge("say_hello", END)
app = graph.compile()
print(app.invoke({"message": "langgraph"}))
```

### LangSmith Studio

- 原文页面：https://docs.langchain.com/oss/python/langgraph/studio
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Prerequisites
  - Set up local Agent server
  - 1. Install the LangGraph CLI
- 最小示例：

```bash
langgraph dev
# 然后把本地 Agent Server 连接到 LangGraph Studio
```

### Test

- 原文页面：https://docs.langchain.com/oss/python/langgraph/test
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Prerequisites
  - Getting started
  - Testing individual nodes and edges
  - Partial execution
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    value: str

def build_graph():
    graph = StateGraph(State)
    graph.add_node("node", lambda state: {"value": "done"})
    graph.add_edge(START, "node")
    graph.add_edge("node", END)
    return graph

def test_graph() -> None:
    app = build_graph().compile(checkpointer=MemorySaver())
    assert app.invoke({"value": "start"}, config={"configurable": {"thread_id": "1"}})["value"] == "done"
```

### Thinking in LangGraph

- 原文页面：https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- 页面定位：这是官方实践/设计页，重点看状态设计、控制流和节点职责划分。
- 官方摘要：Learn how to think about building agents with LangGraph
- 官方页重点：
  - Start with the process you want to automate
  - Step 1: Map out your workflow as discrete steps
  - Step 2: Identify what each step needs to do
  - LLM steps
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    message: str


def say_hello(state: State):
    return {"message": f"hello, {state['message']}"}


graph = StateGraph(State)
graph.add_node("say_hello", say_hello)
graph.add_edge(START, "say_hello")
graph.add_edge("say_hello", END)
app = graph.compile()
print(app.invoke({"message": "langgraph"}))
```

### Agent Chat UI

- 原文页面：https://docs.langchain.com/oss/python/langgraph/ui
- 页面定位：该页关注应用落地、调试、部署和可视化接入。
- 官方页重点：
  - Quick start
  - Local development
  - Connect to your agent
- 最小示例：

```bash
npx create-agent-chat-app --project-name my-langgraph-ui
cd my-langgraph-ui
pnpm install
pnpm dev
```

### Use the functional API

- 原文页面：https://docs.langchain.com/oss/python/langgraph/use-functional-api
- 页面定位：这是 LangGraph API 的核心入口页，重点理解状态、节点、边和执行方式。
- 官方页重点：
  - Creating a simple workflow
  - Parallel execution
  - Calling graphs
  - Call other entrypoints
- 最小示例：

```python
from langgraph.func import entrypoint, task

@task
def multiply(a: int, b: int) -> int:
    return a * b

@entrypoint()
def workflow(payload: dict) -> int:
    return multiply(payload["a"], payload["b"]).result()
```

### Use the graph API

- 原文页面：https://docs.langchain.com/oss/python/langgraph/use-graph-api
- 页面定位：这是 LangGraph API 的核心入口页，重点理解状态、节点、边和执行方式。
- 官方页重点：
  - Setup
  - Define and update state
  - Define state
  - Update state
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    count: int


def inc(state: State):
    return {"count": state["count"] + 1}

app = StateGraph(State).add_node("inc", inc).add_edge(START, "inc").add_edge("inc", END).compile()
print(app.invoke({"count": 0}))
```

### Subgraphs

- 原文页面：https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Setup
  - Define subgraph communication
  - Call a subgraph inside a node
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class ChildState(TypedDict):
    value: str

child = StateGraph(ChildState)
child.add_node("child_node", lambda state: {"value": state["value"].upper()})
child.add_edge(START, "child_node")
child.add_edge("child_node", END)
child_app = child.compile()

parent = StateGraph(ChildState)
parent.add_node("child_graph", child_app)
parent.add_edge(START, "child_graph")
parent.add_edge("child_graph", END)
app = parent.compile()
```

### Use time-travel

- 原文页面：https://docs.langchain.com/oss/python/langgraph/use-time-travel
- 页面定位：该页关注 LangGraph 的长时执行能力，决定图能否暂停、恢复、记忆和回放。
- 官方摘要：Replay past executions and fork to explore alternative paths in LangGraph
- 官方页重点：
  - Overview
  - Replay
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class State(TypedDict):
    topic: str


def node(state: State):
    return {"topic": state["topic"]}

app = StateGraph(State).add_node("node", node).add_edge(START, "node").add_edge("node", END).compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "tt-1"}}
app.invoke({"topic": "jokes"}, config=config)
print(list(app.get_state_history(config)))
```

### Workflows and agents

- 原文页面：https://docs.langchain.com/oss/python/langgraph/workflows-agents
- 页面定位：这是官方实践/设计页，重点看状态设计、控制流和节点职责划分。
- 官方页重点：
  - Setup
  - LLMs and augmentations
- 最小示例：

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    question: str
    route: str


def classify(state: State):
    return {"route": "rag" if "文档" in state["question"] else "chat"}

builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_edge(START, "classify")
builder.add_edge("classify", END)
app = builder.compile()
```

---

## 二、Frontend 页面

### Graph execution

- 原文页面：https://docs.langchain.com/oss/python/langgraph/frontend/graph-execution
- 页面定位：该页关注如何把 LangGraph 的执行过程、节点状态和流式事件渲染到前端。
- 官方摘要：Visualize multi-step graph pipelines with per-node status and streaming content
- 官方页重点：
  - How graph nodes map to UI cards
  - Setting up useStream
  - Routing streaming tokens to nodes
  - Determining node status
- 最小示例：

```tsx
import { useStream } from "@langchain/langgraph-sdk/react-ui";

export function GraphExecutionView() {
  const stream = useStream({ apiUrl: "/api", assistantId: "graph" });
  return <pre>{JSON.stringify(stream.values, null, 2)}</pre>;
}
```

### Overview

- 原文页面：https://docs.langchain.com/oss/python/langgraph/frontend/overview
- 页面定位：该页关注如何把 LangGraph 的执行过程、节点状态和流式事件渲染到前端。
- 官方摘要：Render LangGraph agents to the frontend
- 官方页重点：
  - Architecture
  - Patterns
  - Related patterns
- 最小示例：

```tsx
import { useStream } from "@langchain/langgraph-sdk/react-ui";

export function GraphChat() {
  const stream = useStream({ apiUrl: "/api", assistantId: "graph" });
  return <pre>{JSON.stringify({ messages: stream.messages, values: stream.values }, null, 2)}</pre>;
}
```

---
