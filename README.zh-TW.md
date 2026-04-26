<h1 align="center">agentorch</h1>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">简体中文</a> |
  <a href="README.zh-TW.md">繁體中文</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img alt="Version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="License MIT" src="https://img.shields.io/github/license/Akun-python/agentorch?style=flat-square">
</p>

`agentorch` 是一個以程式碼為核心、以非同步為優先的 Python 智能體編排框架，用於建構可程式化的 agent 系統。

![Architecture Overview](resource/architecture_overview.svg)

## 為什麼使用 agentorch

- Python 原生 API，避免過度依賴提示詞黑盒
- 支援多智能體協調與任務委派
- 支援 RAG、工作流 DAG、記憶治理與可觀測性

## 安裝

```bash
pip install -e .
```

或直接從 GitHub 安裝：

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

## 快速開始

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="你是簡潔且準確的助手。",
    reasoning="react",
)

result = agent.run_sync("請用三句話介紹 agentorch。", thread_id="quickstart-zh-tw-001")
print(result.output_text)
agent.close()
```
