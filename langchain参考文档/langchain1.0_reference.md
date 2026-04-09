# LangChain 1.0 Python 参考文档

生成时间：2026-03-30
来源范围：`https://docs.langchain.com/oss/python/langchain/`

## 文档说明

- 这份文档按官方 LangChain 1.0 Python 文档树整理，共覆盖 58 个页面。
- 每个页面都给出：页面定位、官方页重点、最小示例代码。
- 示例代码是为学习整理而写的最小示例，不是官方文档逐字复制。

## 通用安装

```bash
pip install -U "langchain[openai]" langgraph langsmith pydantic
export OPENAI_API_KEY="sk-..."
```

## 通用基础环境

```python
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
model = init_chat_model("gpt-5.2")
@tool
def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"
agent = create_agent(model=model, tools=[get_weather], system_prompt="You are concise.")
```

---

## 一、根页面

### LangChain Academy

- 原文页面：https://docs.langchain.com/oss/python/langchain/academy
- 页面定位：适合先建立整体认知，再进入具体功能页。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Agents

- 原文页面：https://docs.langchain.com/oss/python/langchain/agents
- 页面定位：这是核心能力页，建议与 create_agent 的最小示例对照阅读。
- 官方页重点：
  - Core components
  - Model
  - Tools
  - System prompt
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="gpt-4.1", tools=[get_weather])
for event in agent.stream({"messages": [{"role": "user", "content": "先查天气，再给出建议"}]}, stream_mode="updates"):
    print(event)
```

### Changelog

- 原文页面：https://docs.langchain.com/oss/python/langchain/changelog-py
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
import platform, langchain
print(langchain.__version__)
print(platform.python_version())
print(platform.platform())
```

### Component architecture

- 原文页面：https://docs.langchain.com/oss/python/langchain/component-architecture
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Core component ecosystem
  - How components connect
  - Component categories
  - Common patterns
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Context engineering in agents

- 原文页面：https://docs.langchain.com/oss/python/langchain/context-engineering
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Overview
  - Why do agents fail?
  - The agent loop
  - What you can control
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### LangSmith Deployment

- 原文页面：https://docs.langchain.com/oss/python/langchain/deploy
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Prerequisites
  - Deploy your agent
  - 1. Create a repository on GitHub
  - 2. Deploy to LangSmith
- 最小示例：

```json
{
  "graphs": {
    "agent": "./app.py:agent"
  },
  "env": ".env"
}
```

### Get help

- 原文页面：https://docs.langchain.com/oss/python/langchain/get-help
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Learning resources
  - Community support
  - Professional support
  - Contribute
- 最小示例：

```python
import platform, langchain
print(langchain.__version__)
print(platform.python_version())
print(platform.platform())
```

### Guardrails

- 原文页面：https://docs.langchain.com/oss/python/langchain/guardrails
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Implement safety checks and content filtering for your agents
- 官方页重点：
  - Built-in guardrails
  - PII detection
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Human-in-the-loop

- 原文页面：https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Interrupt decision types
  - Configuring interrupts
  - Responding to interrupts
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Install LangChain

- 原文页面：https://docs.langchain.com/oss/python/langchain/install
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```bash
pip install -U "langchain[openai]" langgraph langsmith
export OPENAI_API_KEY="sk-..."
```

### Build a semantic search engine with LangChain

- 原文页面：https://docs.langchain.com/oss/python/langchain/knowledge-base
- 页面定位：该页关注外部知识接入，适合构建检索增强系统。
- 官方页重点：
  - Overview
  - Concepts
  - Setup
  - Installation
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
docs = [Document(page_content="退款政策：7 天内可申请退款。")]
retriever = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings()).as_retriever()
ctx = "\n".join(d.page_content for d in retriever.invoke("退款期限"))
print(init_chat_model("gpt-5.2").invoke(f"仅根据上下文回答：{ctx}").content)
```

### Long-term memory

- 原文页面：https://docs.langchain.com/oss/python/langchain/long-term-memory
- 页面定位：该页关注记忆与状态持久化，决定多轮对话能保留多少上下文。
- 官方摘要：Add long-term memory to LangChain agents to store and recall data across conversations and sessions
- 官方页重点：
  - Usage
  - Memory storage
  - Read long-term memory in tools
  - Write long-term memory from tools
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
@tool
def save_pref(value: str, runtime: ToolRuntime) -> str:
    runtime.store.put(("users",), "u-1", {"preference": value})
    return "saved"
agent = create_agent(model="gpt-4.1", tools=[save_pref], store=store)
```

### Model Context Protocol (MCP)

- 原文页面：https://docs.langchain.com/oss/python/langchain/mcp
- 页面定位：这是典型实战页，重点看能力接入方式与运行边界。
- 官方页重点：
  - Quickstart
  - Custom servers
  - Transports
  - HTTP
- 最小示例：

```python
import asyncio
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
async def main():
    client = MultiServerMCPClient({"math": {"transport": "stdio", "command": "python", "args": ["./math_server.py"]}})
    agent = create_agent(model="claude-sonnet-4-6", tools=await client.get_tools())
    print(await agent.ainvoke({"messages": [{"role": "user", "content": "2+2=?"}]}))
asyncio.run(main())
```

### Messages

- 原文页面：https://docs.langchain.com/oss/python/langchain/messages
- 页面定位：这是核心能力页，建议与 create_agent 的最小示例对照阅读。
- 官方页重点：
  - Basic usage
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage
model = init_chat_model("gpt-5.2")
print(model.invoke([SystemMessage("You are concise."), HumanMessage("什么是 LangChain message?")]).content)
```

### Models

- 原文页面：https://docs.langchain.com/oss/python/langchain/models
- 页面定位：这是核心能力页，建议与 create_agent 的最小示例对照阅读。
- 官方页重点：
  - Basic usage
  - Initialize a model
  - Supported models
  - Key methods
- 最小示例：

```python
from langchain.chat_models import init_chat_model
model = init_chat_model("gpt-5.2")
print(model.invoke("Explain LangChain in one sentence.").content)
```

### LangSmith Observability

- 原文页面：https://docs.langchain.com/oss/python/langchain/observability
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Prerequisites
  - Enable tracing
  - Quickstart
- 最小示例：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=langchain-reference
```

### LangChain overview

- 原文页面：https://docs.langchain.com/oss/python/langchain/overview
- 页面定位：适合先建立整体认知，再进入具体功能页。
- 官方摘要：LangChain is an open source framework with a prebuilt agent architecture and integrations for any model or tool—so you can build agents that adapt as fast as the ecosystem evolves
- 官方页重点：
  - <Icon icon="wand" /> Create an agent
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Philosophy

- 原文页面：https://docs.langchain.com/oss/python/langchain/philosophy
- 页面定位：适合先建立整体认知，再进入具体功能页。
- 官方摘要：LangChain exists to be the easiest place to start building with LLMs, while also being flexible and production-ready.
- 官方页重点：
  - History
- 最小示例：

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="claude-sonnet-4-6", tools=[get_weather])
print(agent.invoke({"messages": [{"role": "user", "content": "今天上海天气怎么样？"}]})["messages"][-1].content)
```

### Quickstart

- 原文页面：https://docs.langchain.com/oss/python/langchain/quickstart
- 页面定位：适合第一次跑通 LangChain 1.0 agent。
- 官方页重点：
  - Requirements
  - Build a basic agent
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    return f"{city}: 26C, sunny"

agent = create_agent(model="gpt-4.1", tools=[get_weather])
for event in agent.stream({"messages": [{"role": "user", "content": "先查天气，再给出建议"}]}, stream_mode="updates"):
    print(event)
```

### Build a RAG agent with LangChain

- 原文页面：https://docs.langchain.com/oss/python/langchain/rag
- 页面定位：该页关注外部知识接入，适合构建检索增强系统。
- 官方页重点：
  - Overview
  - Concepts
  - Preview
  - Setup
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
docs = [Document(page_content="退款政策：7 天内可申请退款。")]
retriever = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings()).as_retriever()
ctx = "\n".join(d.page_content for d in retriever.invoke("退款期限"))
print(init_chat_model("gpt-5.2").invoke(f"仅根据上下文回答：{ctx}").content)
```

### Retrieval

- 原文页面：https://docs.langchain.com/oss/python/langchain/retrieval
- 页面定位：该页关注外部知识接入，适合构建检索增强系统。
- 官方页重点：
  - Building a knowledge base
  - From retrieval to RAG
  - Retrieval pipeline
  - Building blocks
- 最小示例：

```python
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
docs = [Document(page_content="退款政策：7 天内可申请退款。")]
retriever = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings()).as_retriever()
ctx = "\n".join(d.page_content for d in retriever.invoke("退款期限"))
print(init_chat_model("gpt-5.2").invoke(f"仅根据上下文回答：{ctx}").content)
```

### Runtime

- 原文页面：https://docs.langchain.com/oss/python/langchain/runtime
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Overview
  - Access
  - Inside tools
  - Inside middleware
- 最小示例：

```python
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
@dataclass
class Context:
    user_name: str
@tool
def read_profile(runtime: ToolRuntime[Context]) -> str:
    return runtime.context.user_name
agent = create_agent(model="gpt-5-nano", tools=[read_profile], context_schema=Context)
```

### Short-term memory

- 原文页面：https://docs.langchain.com/oss/python/langchain/short-term-memory
- 页面定位：该页关注记忆与状态持久化，决定多轮对话能保留多少上下文。
- 官方页重点：
  - Overview
  - Usage
  - In production
  - Customizing agent memory
- 最小示例：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
agent = create_agent(model="gpt-4.1", tools=[], checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "thread-001"}}
agent.invoke({"messages": [{"role": "user", "content": "记住我叫 Alice"}]}, config=config)
```

### Build a SQL agent

- 原文页面：https://docs.langchain.com/oss/python/langchain/sql-agent
- 页面定位：这是典型实战页，重点看能力接入方式与运行边界。
- 官方页重点：
  - Overview
  - Concepts
  - Setup
  - Installation
- 最小示例：

```python
import sqlite3
from langchain.agents import create_agent
from langchain.tools import tool
conn = sqlite3.connect(":memory:")
conn.execute("create table sales (product text, amount int)")
@tool
def run_sql(query: str) -> str:
    return str(conn.execute(query).fetchall())
agent = create_agent(model="gpt-4.1", tools=[run_sql], system_prompt="Write safe read-only SQL.")
```

### Streaming

- 原文页面：https://docs.langchain.com/oss/python/langchain/streaming
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方摘要：Stream real-time updates from agent runs
- 官方页重点：
  - Overview
  - Supported stream modes
  - Agent progress
  - LLM tokens
- 最小示例：

```python
from langchain.agents import create_agent
agent = create_agent(model="gpt-4.1", tools=[])
for chunk in agent.stream({"messages": [{"role": "user", "content": "Explain streaming in 3 steps"}]}, stream_mode=["updates", "messages"]):
    print(chunk)
```

### Structured output

- 原文页面：https://docs.langchain.com/oss/python/langchain/structured-output
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Response format
  - Provider strategy
  - Tool calling strategy
  - Custom tool message content
- 最小示例：

```python
from pydantic import BaseModel
from langchain.agents import create_agent
class Ticket(BaseModel):
    priority: str
    owner: str
agent = create_agent(model="gpt-4.1", tools=[], response_format=Ticket)
print(agent.invoke({"messages": [{"role": "user", "content": "创建高优先级工单给 ops"}]})["structured_response"])
```

### LangSmith Studio

- 原文页面：https://docs.langchain.com/oss/python/langchain/studio
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Prerequisites
  - Set up local Agent server
  - 1. Install the LangGraph CLI
- 最小示例：

```json
{
  "graphs": {
    "agent": "./app.py:agent"
  },
  "env": ".env"
}
```

### Tools

- 原文页面：https://docs.langchain.com/oss/python/langchain/tools
- 页面定位：这是核心能力页，建议与 create_agent 的最小示例对照阅读。
- 官方页重点：
  - Create tools
  - Basic tool definition
  - Customize tool properties
  - Advanced schema definition
- 最小示例：

```python
from langchain.tools import tool
@tool
def search_orders(order_id: str) -> str:
    return f"order={order_id}, status=shipped"
print(search_orders.invoke({"order_id": "SO-1001"}))
```

### Agent Chat UI

- 原文页面：https://docs.langchain.com/oss/python/langchain/ui
- 页面定位：适合作为功能参考页，快速确认能力定位、连接点和最小用法。
- 官方页重点：
  - Quick start
  - Local development
  - Connect to your agent
- 最小示例：

```bash
npx create-agent-chat-app --project-name my-chat-ui
cd my-chat-ui
pnpm install
pnpm dev
```

### Build a voice agent with LangChain

- 原文页面：https://docs.langchain.com/oss/python/langchain/voice-agent
- 页面定位：这是典型实战页，重点看能力接入方式与运行边界。
- 官方页重点：
  - Overview
  - What are voice agents?
  - How do voice agents work?
  - Demo Application overview
- 最小示例：

```python
from fastapi import FastAPI, WebSocket
from langchain.chat_models import init_chat_model
app = FastAPI()
model = init_chat_model("gpt-4.1")
@app.websocket("/voice")
async def voice(ws: WebSocket):
    await ws.accept()
    text = await ws.receive_text()
    await ws.send_text(model.invoke(text).content)
```

---

## 二、Frontend 子页面

### Branching chat

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/branching-chat
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Edit messages, regenerate responses, and navigate conversation branches
- 官方页重点：
  - What is branching chat?
  - Set up useStream with history
  - Understand message metadata
  - Edit a message
- 最小示例：

```tsx
import { useState } from "react";
export function BranchingChat() {
  const [branches, setBranches] = useState({ root: ["original"] });
  return <button onClick={() => setBranches((b) => ({ ...b, retry: ["edited"] }))}>Fork</button>;
}
```

### Generative UI

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/generative-ui
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Render AI-generated user interfaces using json-render
- 官方页重点：
  - How it works
  - Define a component catalog
  - Build a component registry
  - Connect to the agent
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Human-in-the-Loop

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Add approval workflows with interrupt-based human review
- 官方页重点：
  - How interrupts work
  - Setting up useStream for HITL
  - The interrupt payload
  - Decision types
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Join & rejoin streams

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/join-rejoin
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Disconnect from and reconnect to running agent streams
- 官方页重点：
  - Why join & rejoin?
  - Core concepts
  - Setting up useStream
  - Submitting with resumable options
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Markdown messages

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/markdown-messages
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Render LLM responses as rich, formatted markdown with proper streaming support
- 官方页重点：
  - How markdown rendering works
  - Setting up useStream
  - Choosing a markdown library
  - Building the Markdown component
- 最小示例：

```tsx
import ReactMarkdown from "react-markdown";
export function MarkdownMessage({ content }: { content: string }) {
  return <ReactMarkdown>{content}</ReactMarkdown>;
}
```

### Message queues

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/message-queues
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Queue multiple messages and manage them while the agent processes sequentially
- 官方页重点：
  - Why message queues?
  - How it works
  - Setting up useStream
  - Displaying the queue
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Overview

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/overview
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Build generative UIs with real-time streaming from LangChain agents
- 官方页重点：
  - Architecture
  - Patterns
  - Render messages and output
  - Display agent actions
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Reasoning tokens

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/reasoning-tokens
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Display model thinking and reasoning processes in collapsible blocks
- 官方页重点：
  - What are reasoning tokens?
  - Use cases
  - Extracting reasoning and text blocks
  - Accessing messages from useStream
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Structured output

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/structured-output
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Render structured agent responses with custom UI components instead of plain text
- 官方页重点：
  - What is structured output?
  - Use cases
  - Define a schema
  - Extract structured output from messages
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Time travel

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/time-travel
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Inspect, navigate, and resume from any checkpoint in the conversation history
- 官方页重点：
  - How checkpoints work
  - Setting up useStream
  - The ThreadState object
  - Building a checkpoint timeline
- 最小示例：

```tsx
import { useEffect, useState } from "react";

export function AgentPanel() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/agent-stream");
    ws.onmessage = (event) => setEvents((current) => [...current, JSON.parse(event.data)]);
    return () => ws.close();
  }, []);
  return <pre>{JSON.stringify(events, null, 2)}</pre>;
}
```

### Tool calling

- 原文页面：https://docs.langchain.com/oss/python/langchain/frontend/tool-calling
- 页面定位：该页关注前端如何消费 agent 事件并渲染交互界面。
- 官方摘要：Display agent tool calls with rich, type-safe UI cards
- 官方页重点：
  - How tool calling works
  - Setting up useStream
  - The ToolCallWithResult type
  - Filtering tool calls per message
- 最小示例：

```tsx
type ToolCall = { name: string; status: "running" | "done"; input: unknown };
export function ToolCallCard({ call }: { call: ToolCall }) {
  return <div><strong>{call.name}</strong><pre>{JSON.stringify(call.input, null, 2)}</pre></div>;
}
```

---

## 三、Middleware 子页面

### Prebuilt middleware

- 原文页面：https://docs.langchain.com/oss/python/langchain/middleware/built-in
- 页面定位：该页关注如何在 agent 生命周期中注入控制逻辑。
- 官方摘要：Prebuilt middleware for common agent use cases
- 官方页重点：
  - Provider-agnostic middleware
  - Summarization
  - Human-in-the-loop
  - Model call limit
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
agent = create_agent(model="gpt-4.1", tools=[], middleware=[SummarizationMiddleware(model="gpt-4.1-mini", trigger={"tokens": 4000}, keep={"messages": 20})])
```

### Custom middleware

- 原文页面：https://docs.langchain.com/oss/python/langchain/middleware/custom
- 页面定位：该页关注如何在 agent 生命周期中注入控制逻辑。
- 官方页重点：
  - Hooks
  - Node-style hooks
  - Wrap-style hooks
  - State updates
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import AgentState, before_model
from langgraph.runtime import Runtime
@before_model
def log_input(state: AgentState, runtime: Runtime):
    print(len(state["messages"]))
    return None
agent = create_agent(model="gpt-4.1", tools=[], middleware=[log_input])
```

### Overview

- 原文页面：https://docs.langchain.com/oss/python/langchain/middleware/overview
- 页面定位：该页关注如何在 agent 生命周期中注入控制逻辑。
- 官方摘要：Control and customize agent execution at every step
- 官方页重点：
  - The agent loop
  - Additional resources
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
agent = create_agent(model="gpt-4.1", tools=[], middleware=[SummarizationMiddleware(model="gpt-4.1-mini", trigger={"tokens": 4000}, keep={"messages": 20})])
```

---

## 四、Multi-agent 子页面

### Custom workflow

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Key characteristics
  - When to use
  - Basic implementation
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

### Handoffs

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Key characteristics
  - When to use
  - Basic implementation
  - Implementation approaches
- 最小示例：

```python
from typing import Literal, TypedDict
class FlowState(TypedDict):
    active_agent: Literal["triage", "billing", "tech"]
    user_input: str
def handoff(state: FlowState) -> FlowState:
    return {**state, "active_agent": "billing" if "发票" in state["user_input"] else "tech"}
```

### Build customer support with handoffs

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Setup
  - Installation
  - LangSmith
  - Select an LLM
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

### Multi-agent

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/index
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Why multi-agent?
  - Patterns
  - Choosing a pattern
  - Visual overview
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

### Router

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/router
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Key characteristics
  - When to use
  - Basic implementation
  - Stateless vs. stateful
- 最小示例：

```python
from typing import TypedDict
from langgraph.types import Command
class State(TypedDict):
    query: str
def route_query(state: State) -> Command:
    target = "finance_agent" if "预算" in state["query"] else "support_agent"
    return Command(goto=target)
```

### Build a multi-source knowledge base with routing

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/router-knowledge-base
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Overview
  - Why use a router?
  - Concepts
  - Setup
- 最小示例：

```python
from langgraph.types import Send
def route_to_sources(query: str) -> list[Send]:
    names = ["policy_kb", "product_kb"] if "对比" in query else ["policy_kb"]
    return [Send(name, {"query": query}) for name in names]
```

### Skills

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/skills
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Key characteristics
  - When to use
  - Basic implementation
  - Extending the pattern
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
SKILLS = {"write_sql": "Return safe read-only SQL."}
@tool
def load_skill(name: str) -> str:
    return SKILLS[name]
agent = create_agent(model="gpt-4.1", tools=[load_skill])
```

### Build a SQL assistant with on-demand skills

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/skills-sql-assistant
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - How it works
  - Setup
  - Installation
  - LangSmith
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

### Subagents

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/subagents
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Key characteristics
  - When to use
  - Basic implementation
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

### Build a personal assistant with subagents

- 原文页面：https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant
- 页面定位：该页关注多智能体模式下的职责拆分、路由与上下文控制。
- 官方页重点：
  - Overview
  - Why use a supervisor?
  - Concepts
  - Setup
- 最小示例：

```python
from langchain.agents import create_agent
from langchain.tools import tool
specialist = create_agent(model="gpt-4.1", tools=[])
@tool
def ask_specialist(question: str) -> str:
    return specialist.invoke({"messages": [{"role": "user", "content": question}]})["messages"][-1].content
supervisor = create_agent(model="gpt-4.1", tools=[ask_specialist])
```

---

## 五、测试页面

### Evals

- 原文页面：https://docs.langchain.com/oss/python/langchain/test/evals
- 页面定位：该页关注如何验证 agent 行为，减少回归问题。
- 官方摘要：Evaluate agent trajectories using deterministic matching or LLM-as-judge evaluators with AgentEvals and LangSmith.
- 官方页重点：
  - Install AgentEvals
  - Trajectory match evaluator
  - LLM-as-judge evaluator
  - Async support
- 最小示例：

```python
from agentevals.trajectory.match import create_trajectory_match_evaluator
evaluator = create_trajectory_match_evaluator(mode="superset")
print(evaluator(outputs={"trajectory": [{"tool": "search_docs"}]}, reference_outputs={"trajectory": [{"tool": "search_docs"}]})["score"])
```

### Test

- 原文页面：https://docs.langchain.com/oss/python/langchain/test/index
- 页面定位：该页关注如何验证 agent 行为，减少回归问题。
- 官方摘要：Strategies for testing LangChain agents, including unit tests, integration tests, and trajectory evaluations.
- 官方页重点：该页以概览或资源入口为主，建议结合原文阅读。
- 最小示例：

```python
from langchain.agents import create_agent
def test_agent_smoke():
    agent = create_agent(model="gpt-4.1", tools=[])
    assert agent.invoke({"messages": [{"role": "user", "content": "hello"}]})["messages"]
```

### Integration testing

- 原文页面：https://docs.langchain.com/oss/python/langchain/test/integration-testing
- 页面定位：该页关注如何验证 agent 行为，减少回归问题。
- 官方摘要：Test agents with real LLM APIs by organizing tests, managing keys, handling flakiness, and controlling costs.
- 官方页重点：
  - Separate unit and integration tests
  - Manage API keys
  - Assert on structure, not content
  - Reduce cost and latency
- 最小示例：

```python
import os, pytest
from langchain.agents import create_agent
@pytest.mark.integration
def test_real_model_roundtrip():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    agent = create_agent(model="gpt-4.1", tools=[])
    assert agent.invoke({"messages": [{"role": "user", "content": "hello"}]})["messages"]
```

### Unit testing

- 原文页面：https://docs.langchain.com/oss/python/langchain/test/unit-testing
- 页面定位：该页关注如何验证 agent 行为，减少回归问题。
- 官方摘要：Test agent logic without API calls using fake chat models and in-memory persistence.
- 官方页重点：
  - Mock chat model
- 最小示例：

```python
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
model = GenericFakeChatModel(messages=iter(["hello from fake model"]))
agent = create_agent(model=model, tools=[])
assert agent.invoke({"messages": [{"role": "user", "content": "hello"}]})["messages"]
```

---
