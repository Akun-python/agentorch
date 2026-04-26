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

`agentorch`는 코드 중심, 비동기 중심의 Python 멀티에이전트 오케스트레이션 프레임워크입니다.

## WHY

- 프롬프트 블랙박스 대신 유지보수 가능한 시스템 구성
- 모델, 도구, 메모리, RAG, 워크플로 경계를 명확히 분리
- 단일 에이전트에서 다중 역할 팀으로 자연스럽게 확장

## WHAT

- 파사드 API: `create_agent(...)`, `create_multi_agent(...)`
- 구조화된 도구 호출과 샌드박스 실행
- RAG, 메모리 거버넌스, Workflow DAG, 관측성

## HOW

```bash
pip install -e .
```

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Python `3.10+`가 필요합니다.

## QUICKSTART

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="간결하고 정확한 도우미처럼 응답하세요.",
    reasoning="react",
)

result = agent.run_sync("agentorch를 3가지 핵심으로 설명해 주세요.", thread_id="quickstart-ko-001")
print(result.output_text)
agent.close()
```
