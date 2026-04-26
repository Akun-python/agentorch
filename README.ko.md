<h1 align="center">agentorch</h1>

<p align="center">
  <img src="resource/agentorch-icon.svg" alt="agentorch icon" width="110">
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">zh-CN</a> |
  <a href="README.zh-TW.md">zh-TW</a> |
  <a href="README.fr.md">fr</a> |
  <a href="README.ja.md">ja</a> |
  <a href="README.ko.md">ko</a> |
  <a href="README.es.md">es</a>
</p>

<p align="center">
  <img alt="version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="license MIT" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square">
</p>

`agentorch`는 코드 중심, 비동기 중심의 Python 멀티에이전트 오케스트레이션 프레임워크입니다.

프롬프트 블랙박스가 아니라, 경계가 명확한 런타임 구조를 만들기 위해 설계되었습니다.

도구 호출, 검색 근거, 메모리, 워크플로, 다중 에이전트 위임이 동시에 필요한 시스템에서 `agentorch`는 제어 가능한 실행 모델을 제공합니다.

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### 왜 필요한가 🎯

"단일 에이전트 + 단일 프롬프트" 접근은 초기에는 빠르지만, 시스템이 커지면 다음 문제가 생깁니다:

- 역할이 늘어나면 책임 경계가 흐려짐
- 도구가 늘어나면 보안 통제가 어려워짐
- 컨텍스트가 길어지면 상태 추적이 어려워짐
- 검색 결과의 근거 검증이 어려워짐

`agentorch`는 이를 코드 구조로 명시화합니다.

### 엔지니어링 관점 가치 🧭

- 런타임 조립 결과를 내보내고 점검 가능
- 정책 객체를 버전 관리 가능
- 단일 에이전트에서 팀 구조로 점진 확장 가능
- 추론/RAG/워크플로 전략을 안전하게 반복 가능

### 연구 관점 가치 🔬

- 추론 전략 전환 가능 (`react`, `plan_execute` 등)
- RAG/컨텍스트 전략 비교 실험 가능
- 진화 탐색 기반 구성 실험 가능
- 장기 작업 상태 유지 및 재사용 가능

### 대표 사용 시나리오

- 개발 보조: 파일/명령/Git 도구 제어
- 지식 보조: 근거 인용이 필요한 답변
- 자동화: DAG 노드 단위 실행 제어
- 장기 태스크: 스레드/워크스페이스 메모리 활용

## WHAT

### 핵심 진입 API

- `create_agent(...)`
- `create_multi_agent(...)`

대부분의 프로젝트는 위 facade API로 시작하는 것이 좋습니다.

### 주요 런타임 구성요소 🧩

- 모델 어댑터 계층
- 도구 레지스트리와 번들
- 샌드박스 실행과 정책
- 지식베이스와 RAG 전략
- 메모리 관리와 거버넌스
- DAG 워크플로 실행
- 관측성 이벤트 및 저장

### 여기서 오케스트레이션이 의미하는 것

`agentorch`에서 오케스트레이션은 추상 개념이 아니라 명시적 구조입니다:

- Commander가 라우팅과 위임 담당
- Task packet은 타입이 있는 실행 단위
- Handoff는 추적 가능한 기록
- 공유 메모리는 정책으로 관리
- 도구 노출 범위는 제한 가능

### 호환성과 안정성

- Python `3.10+`
- 핵심 의존성 최소화
- 고수준 facade API 안정화
- 기존 통합을 위한 호환 export 제공

## HOW

### 설치 📦

로컬 editable 설치:

```bash
pip install -e .
```

GitHub 직접 설치:

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

선택 의존성 예:

```bash
pip install -e ".[neo4j]"
```

### 환경 변수

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`.env`는 명시적으로 로드하는 방식을 권장합니다.

### 권장 도입 순서

1. 단일 에이전트 경로 먼저 안정화
2. 도구는 최소 권한으로 추가
3. RAG는 근거 품질 확인 후 활성화
4. 마지막에 다중 에이전트 위임 도입

### 검증 명령

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### 운영 가드레일 ✅

- 도구 allowlist 최소화
- thread_id를 명시해 추적성 확보
- 긴 작업은 단계로 분할
- 실행 종료 시 agent/runtime 명시적 close

## QUICKSTART

### 1) 최소 실행 예제

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="간결하고 정확한 도우미처럼 응답하세요.",
    reasoning="react",
)

result = agent.run_sync(
    "에이전트 오케스트레이션이 무엇인지 3가지 핵심으로 설명해 주세요.",
    thread_id="quickstart-ko-001",
)

print(result.output_text)
agent.close()
```

### 2) 도구 호출 예제

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool

class AddInput(BaseModel):
    a: int
    b: int

@tool(description="Add two integers.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}

agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync("add_numbers로 12 + 30을 계산해 주세요.", thread_id="quickstart-tools-ko-001")
print(result.output_text)
agent.close()
```

### 3) 멀티에이전트 시작 예제

```python
from agentorch import create_agent, create_multi_agent

planner = create_agent(model="gpt-4.1-mini", reasoning="plan_execute", name="planner")
reviewer = create_agent(model="gpt-4.1-mini", reasoning="react", name="reviewer")

team = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {"agent": planner, "name": "planner", "role": "planner"},
        {"agent": reviewer, "name": "reviewer", "role": "reviewer"},
    ],
    system_prompt="전문 에이전트를 조율해 하나의 최종 답변을 반환하세요.",
)

result = team.run_sync("마이그레이션 계획을 작성하고 리뷰해 주세요.", thread_id="quickstart-team-ko-001")
print(result.output_text)
team.close()
```

### 4) 다음 단계

- `knowledge_paths` + `enable_rag=True` 적용
- 순서 제어가 필요하면 workflow DAG 도입
- observability로 비용/품질 분석
- 정책 객체를 코드에 고정해 재현성 확보

MIT License.
