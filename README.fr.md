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

`agentorch` est un framework Python orienté code et asynchrone pour orchestrer des systèmes multi-agents.

## WHY

- Éviter les pipelines cachés basés uniquement sur des prompts.
- Garder des frontières claires: modèle, outils, mémoire, RAG, workflow.
- Passer facilement d’un agent à une équipe d’agents spécialisés.

## WHAT

- API façade: `create_agent(...)`, `create_multi_agent(...)`
- Appels d’outils structurés et exécution sandboxée
- RAG, mémoire, workflow DAG, observabilité

## HOW

```bash
pip install -e .
```

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Python `3.10+` requis.

## QUICKSTART

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="Tu es un assistant concis et précis.",
    reasoning="react",
)

result = agent.run_sync("Explique agentorch en trois points.", thread_id="quickstart-fr-001")
print(result.output_text)
agent.close()
```
