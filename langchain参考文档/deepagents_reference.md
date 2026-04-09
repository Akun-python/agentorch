# Deep Agents Python 参考文档

生成时间：2026-03-30
来源范围：`https://docs.langchain.com/oss/python/deepagents/`

## 文档说明

- 这份文档按官方 Deep Agents Python 文档树整理，共覆盖 27 个页面。
- 每个页面都给出：页面定位、官方页重点、最小示例代码。
- 示例代码是为学习整理而写的最小示例，不是官方文档逐字复制。

## 通用安装

```bash
pip install -U deepagents langgraph langsmith
export ANTHROPIC_API_KEY="your-api-key"
```

## 通用基础环境

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful deep agent.",
)
```

---

## 一、SDK 与核心页面

### Agent Client Protocol (ACP)

- 原文页面：https://docs.langchain.com/oss/python/deepagents/acp
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Expose Deep Agents over the Agent Client Protocol (ACP) to integrate with code editors and IDEs.
- 官方页重点：
  - Quickstart
  - Clients
  - Zed
  - Toad
- 最小示例：

```python
import asyncio
from acp import run_agent
from deepagents import create_deep_agent
from deepagents_acp.server import AgentServerACP

async def main() -> None:
    agent = create_deep_agent(system_prompt="You are a helpful coding assistant")
    await run_agent(AgentServerACP(agent))

asyncio.run(main())
```

### Async subagents

- 原文页面：https://docs.langchain.com/oss/python/deepagents/async-subagents
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Launch background subagents that run concurrently while the supervisor continues interacting with the user
- 官方页重点：
  - When to use async subagents
  - Configure async subagents
  - Use the async subagent tools
  - Understand the lifecycle
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[
        {"name": "researcher", "description": "Long-running research worker"},
        {"name": "coder", "description": "Background coding worker"},
    ],
)
# 异步子代理通常需要部署环境来启动、查询、更新和取消后台任务。
```

### Backends

- 原文页面：https://docs.langchain.com/oss/python/deepagents/backends
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Choose and configure filesystem backends for Deep Agents. You can specify routes to different backends, implement virtual filesystems, and enforce policies.
- 官方页重点：
  - Quickstart
  - Built-in backends
  - StateBackend (ephemeral)
- 最小示例：

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend


def make_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={"/project/": FilesystemBackend(".")},
    )

agent = create_deep_agent(backend=make_backend)
```

### Changelog

- 原文页面：https://docs.langchain.com/oss/python/deepagents/changelog-py
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
import deepagents
print(deepagents.__version__)
```

### Comparison with Claude Agent SDK and Codex

- 原文页面：https://docs.langchain.com/oss/python/deepagents/comparison
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Compare LangChain Deep Agents with Claude Agent SDK and Codex SDK to choose the right tool for your use case
- 官方页重点：
  - Overview
  - Key differences
  - Feature comparison
  - Notice a mistake?
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful deep agent.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "总结一下 Deep Agents 的核心能力"}]})
print(result["messages"][-1].content)
```

### Context engineering in Deep Agents

- 原文页面：https://docs.langchain.com/oss/python/deepagents/context-engineering
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Control what context your deep agent has access to and how it is managed across long-running tasks
- 官方页重点：
  - Types of context
  - Input context
  - System prompt
  - Memory
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful deep agent.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "总结一下 Deep Agents 的核心能力"}]})
print(result["messages"][-1].content)
```

### Customize Deep Agents

- 原文页面：https://docs.langchain.com/oss/python/deepagents/customization
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Learn how to customize Deep Agents with system prompts, tools, subagents, and more
- 官方页重点：
  - Connection resilience
  - Model
  - Tools
  - System prompt
- 最小示例：

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model


def get_policy(topic: str) -> str:
    return f"policy for {topic}"

agent = create_deep_agent(
    model=init_chat_model("openai:gpt-5.2"),
    tools=[get_policy],
    system_prompt="Use tools when needed and keep answers concise.",
    subagents=[{"name": "researcher", "description": "Researches in depth"}],
)
```

### Build a data analysis agent

- 原文页面：https://docs.langchain.com/oss/python/deepagents/data-analysis
- 页面定位：这是官方实战页，重点看任务分解、工具设计和运行环境。
- 官方摘要：Build an agent that analyzes data files, generates visualizations, and shares results
- 官方页重点：
  - Overview
  - Key concepts
  - Setup
  - Installation
- 最小示例：

```python
from deepagents import create_deep_agent


def share_to_slack(channel: str, message: str) -> str:
    return f"shared to {channel}"

agent = create_deep_agent(
    tools=[share_to_slack],
    system_prompt="Analyze the CSV, create plots, and summarize the findings.",
)
```

### Build a deep research agent

- 原文页面：https://docs.langchain.com/oss/python/deepagents/deep-research
- 页面定位：这是官方实战页，重点看任务分解、工具设计和运行环境。
- 官方摘要：Build a multi-step web research agent with subagent delegation
- 官方页重点：
  - Overview
  - Key concepts
  - Prerequisites
  - Setup
- 最小示例：

```python
from deepagents import create_deep_agent


def search_web(query: str) -> str:
    return f"web results for {query}"

agent = create_deep_agent(
    tools=[search_web],
    subagents=[{"name": "researcher", "description": "Performs focused web research"}],
    system_prompt="Plan the research, delegate tasks, and write a cited report.",
)
```

### Harness capabilities

- 原文页面：https://docs.langchain.com/oss/python/deepagents/harness
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Planning capabilities
  - Virtual filesystem access
  - Task delegation (subagents)
  - Context management
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful deep agent.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "总结一下 Deep Agents 的核心能力"}]})
print(result["messages"][-1].content)
```

### Human-in-the-loop

- 原文页面：https://docs.langchain.com/oss/python/deepagents/human-in-the-loop
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Learn how to configure human approval for sensitive tool operations
- 官方页重点：
  - Basic configuration
- 最小示例：

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    interrupt_on={"delete_file": True, "send_email": {"allowed_decisions": ["approve", "reject"]}},
    checkpointer=MemorySaver(),
)
```

### Long-term memory

- 原文页面：https://docs.langchain.com/oss/python/deepagents/long-term-memory
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Learn how to extend Deep Agents with persistent memory across threads
- 官方页重点：
  - Setup
  - How it works
  - 1. Short-term (transient) filesystem
  - 2. Long-term (persistent) filesystem
- 最小示例：

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver

store = InMemoryStore()
checkpointer = MemorySaver()

def make_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={"/memories/": StoreBackend(runtime, store=store)},
    )

agent = create_deep_agent(backend=make_backend, checkpointer=checkpointer)
```

### Models

- 原文页面：https://docs.langchain.com/oss/python/deepagents/models
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方页重点：
  - Pass a model string
  - Configure model parameters
  - Select a model at runtime
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

model = init_chat_model(
    model="anthropic:claude-sonnet-4-6",
    thinking={"type": "enabled", "budget_tokens": 8000},
)
agent = create_deep_agent(model=model)
```

### Deep Agents overview

- 原文页面：https://docs.langchain.com/oss/python/deepagents/overview
- 页面定位：适合先建立 Deep Agents 的整体认知，再进入具体功能页。
- 官方摘要：Build agents that can plan, use subagents, and leverage file systems for complex tasks
- 官方页重点：
  - <Icon icon="wand" /> Create a deep agent
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful deep agent.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "总结一下 Deep Agents 的核心能力"}]})
print(result["messages"][-1].content)
```

### Quickstart

- 原文页面：https://docs.langchain.com/oss/python/deepagents/quickstart
- 页面定位：适合先建立 Deep Agents 的整体认知，再进入具体功能页。
- 官方摘要：Build your first deep agent in minutes
- 官方页重点：
  - Prerequisites
  - Step 1: Install dependencies
  - Step 2: Set up your API keys
  - Step 3: Create a search tool
- 最小示例：

```python
from deepagents import create_deep_agent


def search_web(query: str) -> str:
    return f"search results for: {query}"

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[search_web],
    system_prompt="Research the topic and write a short report.",
)

print(agent.invoke({"messages": [{"role": "user", "content": "研究 Deep Agents 的用途"}]})["messages"][-1].content)
```

### Sandboxes

- 原文页面：https://docs.langchain.com/oss/python/deepagents/sandboxes
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Execute code in isolated environments with sandbox backends
- 官方页重点：
  - Why use sandboxes?
  - Integration patterns
  - Agent in sandbox pattern
  - Sandbox as tool pattern
- 最小示例：

```python
from deepagents import create_deep_agent

sandbox_backend = ...  # 例如某个 sandbox provider 返回的 backend
agent = create_deep_agent(
    backend=sandbox_backend,
    system_prompt="You may inspect files and run commands inside the sandbox.",
)
```

### Skills

- 原文页面：https://docs.langchain.com/oss/python/deepagents/skills
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Learn how to extend your deep agent's capabilities with skills
- 官方页重点：
  - What are skills
  - How skills work
  - Example
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["./skills/langgraph-docs", "./skills/arxiv_search"],
)
```

### Streaming

- 原文页面：https://docs.langchain.com/oss/python/deepagents/streaming
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Stream real-time updates from deep agent runs and subagent execution
- 官方页重点：
  - Enable subgraph streaming
  - Namespaces
  - Subagent progress
  - LLM tokens
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    system_prompt="You are a research assistant.",
    subagents=[{"name": "researcher", "description": "Researches deeply"}],
)

for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "研究量子计算近况"}]},
    stream_mode="updates",
    subgraphs=True,
    version="v2",
):
    print(chunk)
```

### Subagents

- 原文页面：https://docs.langchain.com/oss/python/deepagents/subagents
- 页面定位：这是 Deep Agents 的核心能力页，建议和 `create_deep_agent` 的最小示例对照阅读。
- 官方摘要：Learn how to use subagents to delegate work and keep context clean
- 官方页重点：
  - Why use subagents?
  - Configuration
  - SubAgent (Dictionary-based)
  - CompiledSubAgent
- 最小示例：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[
        {"name": "researcher", "description": "Researches a topic in depth"},
        {"name": "coder", "description": "Writes and explains code"},
    ],
)
```

---

## 二、CLI 页面

### Configuration

- 原文页面：https://docs.langchain.com/oss/python/deepagents/cli/configuration
- 页面定位：该页关注 Deep Agents CLI 的配置、模型接入和外部工具扩展。
- 官方摘要：Configure the Deep Agents CLI with config.toml, hooks, and MCP servers
- 官方页重点：
  - Config file
  - Default and recent model
  - Provider configuration
  - Model constructor params
- 最小示例：

```toml
[models]
default = "anthropic:claude-sonnet-4-6"

[models.providers.openai]
models = ["gpt-5.2"]
api_key_env = "OPENAI_API_KEY"
```

### MCP Tools

- 原文页面：https://docs.langchain.com/oss/python/deepagents/cli/mcp-tools
- 页面定位：该页关注 Deep Agents CLI 的配置、模型接入和外部工具扩展。
- 官方摘要：Load additional tools from MCP (Model Context Protocol) servers
- 官方页重点：
  - Quickstart
  - Auto-discovery
  - Discovery locations
  - Flags
- 最小示例：

```json
{
  "mcpServers": {
    "docs-langchain": {
      "url": "https://docs.langchain.com/mcp"
    }
  }
}
```

### Deep Agents CLI

- 原文页面：https://docs.langchain.com/oss/python/deepagents/cli/overview
- 页面定位：该页关注 Deep Agents CLI 的配置、模型接入和外部工具扩展。
- 官方摘要：Terminal coding agent built on the Deep Agents SDK
- 官方页重点：
  - Quickstart
  - Providers
- 最小示例：

```bash
deepagents
# 在终端里启动 Deep Agents CLI 会话
```

### Custom model providers

- 原文页面：https://docs.langchain.com/oss/python/deepagents/cli/providers
- 页面定位：该页关注 Deep Agents CLI 的配置、模型接入和外部工具扩展。
- 官方摘要：Configure any LangChain-compatible model provider for the Deep Agents CLI
- 官方页重点：
  - Quick start
  - Provider reference
  - Switching models
  - Which models appear in the switcher
- 最小示例：

```toml
[models.providers.local_openai]
models = ["gpt-4.1"]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"
```

---

## 三、Frontend 页面

### Overview

- 原文页面：https://docs.langchain.com/oss/python/deepagents/frontend/overview
- 页面定位：该页关注如何把 Deep Agents 的状态和子代理流渲染到前端。
- 官方摘要：Build UIs that display real-time subagent streams, task progress, and sandbox for Deep Agents
- 官方页重点：
  - Architecture
  - Patterns
  - Related patterns
- 最小示例：

```tsx
import { useStream } from "@langchain/langgraph-sdk/react-ui";

export function DeepAgentChat() {
  const stream = useStream({ apiUrl: "/api", assistantId: "agent" });
  return <pre>{JSON.stringify({ messages: stream.messages, values: stream.values }, null, 2)}</pre>;
}
```

### Sandbox

- 原文页面：https://docs.langchain.com/oss/python/deepagents/frontend/sandbox
- 页面定位：该页关注如何把 Deep Agents 的状态和子代理流渲染到前端。
- 官方摘要：Build an IDE-like UI for a coding agent backed by a sandbox environment
- 官方页重点：
  - Architecture
  - Sandbox lifecycle
  - Thread-scoped sandbox (recommended)
  - Agent-scoped sandbox
- 最小示例：

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/sandbox/{thread_id}/files")
def list_files(thread_id: str):
    return {"thread_id": thread_id, "files": []}
```

### Subagent streaming

- 原文页面：https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming
- 页面定位：该页关注如何把 Deep Agents 的状态和子代理流渲染到前端。
- 官方摘要：Display specialist subagents with streaming content, progress tracking, and collapsible cards
- 官方页重点：
  - Why filter subagent messages
  - Setting up useStream
  - Submitting with subgraph streaming
  - The SubagentStreamInterface
- 最小示例：

```tsx
import { useStream } from "@langchain/langgraph-sdk/react-ui";

export function SubagentCards() {
  const stream = useStream({ apiUrl: "/api", assistantId: "agent", filterSubagentMessages: true });
  return <pre>{JSON.stringify(stream.subagents, null, 2)}</pre>;
}
```

### Todo list

- 原文页面：https://docs.langchain.com/oss/python/deepagents/frontend/todo-list
- 页面定位：该页关注如何把 Deep Agents 的状态和子代理流渲染到前端。
- 官方摘要：Track agent progress with a real-time todo list synced from agent state
- 官方页重点：
  - How it works
  - Setting up useStream
  - The Todo interface
  - Building the TodoList component
- 最小示例：

```tsx
import { useStream } from "@langchain/langgraph-sdk/react-ui";

export function TodoList() {
  const stream = useStream({ apiUrl: "/api", assistantId: "agent" });
  return <pre>{JSON.stringify(stream.values.todos ?? [], null, 2)}</pre>;
}
```

---
