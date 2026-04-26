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
  <img alt="license MIT" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square">
</p>

`agentorch` es un framework de Python orientado a código y asíncrono para orquestación multiagente programable.

Está pensado para sistemas con límites de ingeniería claros, no para cadenas opacas basadas solo en prompts.

Cuando necesitas herramientas, RAG, memoria, workflow y delegación en un mismo sistema, `agentorch` ofrece un modelo de ejecución controlable.

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### Por qué este framework 🎯

Muchos proyectos funcionan al inicio con "un asistente + un prompt", pero al crecer aparecen problemas:

- más roles, menos claridad de responsabilidades
- más herramientas, menos control de seguridad
- más contexto, menor trazabilidad de estado
- más recuperación, menor verificabilidad de evidencia

`agentorch` convierte esos riesgos en estructura de software explícita.

### Valor para equipos de ingeniería 🧭

- ensamblado runtime exportable e inspeccionable
- políticas configurables y versionables
- transición gradual de un agente a varios agentes
- evolución controlada de estrategias de razonamiento/RAG/workflow

### Valor para equipos de investigación 🔬

- cambio de estrategias de razonamiento (`react`, `plan_execute`, etc.)
- comparación de variantes de RAG y contexto
- búsqueda evolutiva de configuraciones
- reutilización de estado en tareas de largo horizonte

### Casos de uso típicos

- asistentes de desarrollo con acceso acotado a archivos/comandos/Git
- asistentes de conocimiento con citas de evidencia
- automatizaciones con ejecución DAG explícita
- asistentes de larga duración con memoria multi-sesión

## WHAT

### API principal (fachada)

- `create_agent(...)`
- `create_multi_agent(...)`

Son los puntos de entrada recomendados para la mayoría de aplicaciones.

### Bloques clave del runtime 🧩

- adaptadores de modelo
- registro de herramientas y bundles
- sandbox y políticas de ejecución
- base de conocimiento y estrategias RAG
- gestión de memoria y gobernanza
- workflow DAG y runner
- observabilidad y almacenamiento de eventos

### Qué significa "orquestación" aquí

En `agentorch`, orquestación es algo concreto:

- el Commander enruta y delega
- los task packets son unidades tipadas
- los handoffs quedan registrados
- la memoria compartida está gobernada por políticas
- la superficie de herramientas se controla de forma explícita

### Compatibilidad

- Python `3.10+`
- dependencias core reducidas
- API de fachada estable para uso diario
- exports de compatibilidad para migración

## HOW

### Instalación 📦

Instalación editable local:

```bash
pip install -e .
```

Instalación directa desde GitHub:

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Ejemplo de extra opcional:

```bash
pip install -e ".[neo4j]"
```

### Variables de entorno

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Se recomienda cargar `.env` de forma explícita.

### Orden recomendado de adopción

1. estabiliza primero un agente único
2. añade herramientas con permisos mínimos
3. activa RAG y valida calidad de evidencia
4. incorpora delegación multiagente después

### Comandos de validación

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### Guardrails prácticos ✅

- allowlist de herramientas lo más pequeña posible
- thread_id explícito para trazabilidad
- tareas largas divididas en pasos auditables
- cierre explícito de agent/runtime al finalizar

## QUICKSTART

### 1) Ejemplo mínimo

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="Eres un asistente conciso y preciso.",
    reasoning="react",
)

result = agent.run_sync(
    "Explica qué es la orquestación de agentes en tres puntos clave.",
    thread_id="quickstart-es-001",
)

print(result.output_text)
agent.close()
```

### 2) Ejemplo de llamada de herramienta

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

result = agent.run_sync("Usa add_numbers para calcular 12 + 30.", thread_id="quickstart-tools-es-001")
print(result.output_text)
agent.close()
```

### 3) Ejemplo inicial multiagente

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
    system_prompt="Coordina especialistas y devuelve una respuesta final.",
)

result = team.run_sync("Diseña y revisa una estrategia de migración.", thread_id="quickstart-team-es-001")
print(result.output_text)
team.close()
```

### 4) Siguientes pasos

- agregar `knowledge_paths` y `enable_rag=True`
- incorporar workflow DAG para secuencias deterministas
- activar observabilidad para analizar costo/calidad
- fijar políticas runtime en configuración versionada

MIT License.
