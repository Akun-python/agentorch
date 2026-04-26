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

`agentorch` 是一個程式碼優先、非同步優先的 Python 多智能體編排框架。

## WHY

- 避免提示詞黑盒，保持系統可維護。
- 模型、工具、記憶、RAG、工作流邊界清晰。
- 可從單智能體擴展到多角色協作。

## WHAT

- 高階 API：`create_agent(...)`、`create_multi_agent(...)`
- 結構化工具調用與沙箱執行
- RAG、記憶治理、工作流 DAG、可觀測性

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
    system_prompt="你是簡潔且準確的助手。",
    reasoning="react",
)

result = agent.run_sync("請用三個重點介紹 agentorch。", thread_id="quickstart-zh-tw-001")
print(result.output_text)
agent.close()
```
