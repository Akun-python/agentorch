<h1 align="center">agentorch</h1>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">简体中文</a> |
  <a href="README.zh-TW.md">繁體中文</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.es.md">Español</a>
</p>

<p align="center">
  <img alt="version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="license MIT" src="https://img.shields.io/github/license/Akun-python/agentorch?style=flat-square">
</p>

`agentorch` 是一个代码优先、异步优先的 Python 多智能体编排框架。

## WHY

- 不是提示词黑盒，而是可编程、可维护的系统。
- 编排边界清晰：模型、工具、记忆、RAG、工作流。
- 可从单智能体扩展到多角色协作团队。

## WHAT

- 高层 API：`create_agent(...)`、`create_multi_agent(...)`
- 结构化工具调用与沙箱执行
- RAG、记忆治理、工作流 DAG、可观测性
- 可切换推理策略与进化搜索

## HOW

```bash
pip install -e .
```

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

需要 Python `3.10+`。

## QUICKSTART

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="你是一个简洁且准确的助手。",
    reasoning="react",
)

result = agent.run_sync("请用三个要点介绍 agentorch。", thread_id="quickstart-zh-cn-001")
print(result.output_text)
agent.close()
```
