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

`agentorch` は、コードファーストかつ非同期ファーストで設計された Python のマルチエージェント・オーケストレーションフレームワークです。

![Architecture Overview](resource/architecture_overview.svg)

## agentorch を使う理由

- Python ネイティブ API による明示的なランタイム構成
- マルチエージェントの委譲・協調
- 構造化ツール呼び出し、Sandbox、RAG、長期メモリ

## インストール

```bash
pip install -e .
```

GitHub から直接インストール：

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

## クイックスタート

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="簡潔で正確なアシスタントとして振る舞ってください。",
    reasoning="react",
)

result = agent.run_sync("agentorch を 3 文で説明してください。", thread_id="quickstart-ja-001")
print(result.output_text)
agent.close()
```
