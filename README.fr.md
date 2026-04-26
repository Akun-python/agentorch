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

`agentorch` est un framework Python orienté code et asynchrone pour l’orchestration multi-agents programmable.

Il vise les systèmes où les limites d’ingénierie doivent rester explicites, au-delà des chaînes de prompts opaques.

Quand votre cas d’usage combine outils, RAG, mémoire, workflow et délégation d’agents, `agentorch` fournit un modèle d’exécution contrôlable.

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### Pourquoi ce framework 🎯

Après la phase "un assistant + un prompt", beaucoup de systèmes deviennent difficiles à maintenir :

- rôles multiples sans frontières nettes
- outils puissants mais peu gouvernés
- contexte long et état difficile à tracer
- recherche documentaire sans chaîne de preuve fiable

`agentorch` transforme ces problèmes en structure logicielle explicite.

### Valeur pour l’ingénierie 🧭

- assemblage runtime exportable et inspectable
- politiques versionnables et testables
- migration progressive d’un agent vers un système multi-agents
- itération contrôlée des stratégies (raisonnement, RAG, workflow)

### Valeur pour la recherche 🔬

- stratégies de raisonnement interchangeables
- comparaison de variantes RAG/contexte
- support de recherche évolutive
- conservation d’état pour tâches longues

### Cas d’usage typiques

- assistants de développement avec accès outils borné
- assistants knowledge qui citent les preuves
- automatisations pilotées par DAG explicite
- assistants long-horizon avec mémoire multi-session

## WHAT

### API façade principale

- `create_agent(...)`
- `create_multi_agent(...)`

Ces points d’entrée couvrent la majorité des besoins applicatifs.

### Blocs runtime clés 🧩

- adaptateurs de modèles
- registre d’outils et bundles
- sandbox + politique d’exécution
- base de connaissance + stratégies RAG
- gestion mémoire + gouvernance
- DAG workflow + runner
- observabilité + stockage d’événements

### Ce que signifie "orchestration"

Dans `agentorch`, l’orchestration est explicite :

- le commander route et délègue
- les task packets sont typés
- les handoffs sont traçables
- la mémoire partagée est gouvernée
- la surface des outils est contrôlée

### Compatibilité

- Python `3.10+`
- dépendances cœur limitées
- surface API stable côté façade
- exports de compatibilité pour migration

## HOW

### Installation 📦

Installation locale editable :

```bash
pip install -e .
```

Installation directe depuis GitHub :

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

Exemple d’extra optionnel :

```bash
pip install -e ".[neo4j]"
```

### Variables d’environnement

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Préférez un chargement explicite de `.env`.

### Ordre de mise en place recommandé

1. Stabiliser un agent unique.
2. Ajouter les outils avec permissions minimales.
3. Ajouter RAG après validation qualité des preuves.
4. Introduire la délégation multi-agents ensuite.

### Commandes de validation

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### Garde-fous pratiques ✅

- whitelist outils minimale
- IDs de threads explicites
- tâches longues découpées en étapes auditables
- fermeture explicite des agents/runtimes

## QUICKSTART

### 1) Agent minimal

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="Tu es un assistant concis et précis.",
    reasoning="react",
)

result = agent.run_sync(
    "Explique ce qu'est l'orchestration d'agents en trois points.",
    thread_id="quickstart-fr-001",
)

print(result.output_text)
agent.close()
```

### 2) Appel d’outil

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

result = agent.run_sync("Utilise add_numbers pour calculer 12 + 30.", thread_id="quickstart-tools-fr-001")
print(result.output_text)
agent.close()
```

### 3) Démarrage multi-agents

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
    system_prompt="Coordonne les spécialistes et fournis une réponse finale.",
)

result = team.run_sync("Planifie puis révise une stratégie de migration.", thread_id="quickstart-team-fr-001")
print(result.output_text)
team.close()
```

### 4) Étapes suivantes

- ajouter `knowledge_paths` + `enable_rag=True`
- introduire un DAG workflow pour verrouiller les séquences
- activer l’observabilité pour coût/qualité
- versionner les politiques runtime

MIT License.
