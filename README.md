<h1 align="center">agentorch</h1>

<p align="center">
  <img src="resource/agentorch-icon.svg" alt="agentorch icon" width="110">
</p>

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

`agentorch` is a code-first, async-first framework for building programmable multi-agent systems in Python.

## WHY

- Build real agent systems, not prompt-only wrappers.
- Keep orchestration explicit: model, tools, memory, RAG, workflow.
- Scale from one agent to coordinated specialist teams.

## WHAT

- Facade API: `create_agent(...)`, `create_multi_agent(...)`
- Structured tool calling and sandboxed execution
- RAG, memory governance, workflow DAGs, observability
- Reasoning strategies and evolution search

## HOW

```bash
pip install -e .
```

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Requires Python `3.10+`.

## QUICKSTART

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="You are concise and accurate.",
    reasoning="react",
)

result = agent.run_sync("Explain agentorch in three bullet points.", thread_id="quickstart-en-001")
print(result.output_text)
agent.close()
```
