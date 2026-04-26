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

`agentorch` es un framework de orquestación multiagente en Python, orientado a código y asíncrono.

## WHY

- Evita pipelines opacos basados solo en prompts
- Mantiene límites claros entre modelo, herramientas, memoria, RAG y workflow
- Escala de un agente a equipos de especialistas

## WHAT

- API de fachada: `create_agent(...)`, `create_multi_agent(...)`
- Llamadas de herramientas estructuradas y ejecución en sandbox
- RAG, memoria, workflow DAG y observabilidad

## HOW

```bash
pip install -e .
```

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Requiere Python `3.10+`.

## QUICKSTART

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="Eres un asistente conciso y preciso.",
    reasoning="react",
)

result = agent.run_sync("Explica agentorch en tres puntos.", thread_id="quickstart-es-001")
print(result.output_text)
agent.close()
```
