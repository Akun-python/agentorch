# AgentTorch Architecture Audit

- Generated on: `2026-04-19`
- Commit: `07f5d01`
- Static evidence: [`metrics.json`](./metrics.json)
- Verification baseline: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 C:\Users\24260\.conda\envs\data_analysis_py311\python.exe -m pytest -q` -> `261 passed, 2 skipped`
- Status note: this narrative captures the pre-refactor audit baseline; the current `refactor/agentorch-architecture-rebuild-20260419` branch has already removed root import-time bootstrap side effects, cleared the bootstrap-registry lazy-default cycles plus the former `runtime.context_compaction <-> strategies` and `evolution.session <-> runtime.*` static cycles, extracted workflow node execution into `agentorch/runtime/workflow_execution.py` so `runtime/runtime.py` is now down to `1725` lines in the latest static snapshot, and re-verified `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 C:\Users\24260\.conda\envs\data_analysis_py311\python.exe -m pytest -q` at `267 passed, 2 skipped`.

## Executive Conclusion

`AgentTorch` is **not** currently a cleanly layered base framework. It is best described as a **monolithic framework kernel packaged behind a very wide facade-style public API**.

The framework is functional and broadly testable, but its current shape concentrates too much responsibility into four hotspots:

- [`agentorch/__init__.py`](../../agentorch/__init__.py)
- [`agentorch/facade.py`](../../agentorch/facade.py)
- [`agentorch/runtime/runtime.py`](../../agentorch/runtime/runtime.py)
- [`agentorch/config/settings.py`](../../agentorch/config/settings.py)

That concentration is no longer just a style issue. It is now affecting import behavior, configuration determinism, dependency direction, and test trustworthiness.

## Evidence Snapshot

### Public API and import-time side effects

- Root `agentorch.__all__` size: `256`
- Root `agentorch/__init__.py` line count: `508`
- Top-level import side effects in `agentorch/__init__.py`:
  - `bootstrap_reasoning_defaults()`
  - `bootstrap_evolution_defaults()`
  - `bootstrap_memory_defaults()`
- Top-level import side effects in [`agentorch/models/__init__.py`](../../agentorch/models/__init__.py):
  - `register_model_provider("openai", ...)`
  - `register_model_provider("openai_http", ...)`
- Fresh interpreter import confirms registries are populated immediately after `import agentorch`:
  - reasoning: `['cot', 'legacy_policy', 'plan_execute', 'react', 'reflexion', 'tot']`
  - memory backends: `['in_memory_state_store', 'sqlite_checkpoint_store', 'sqlite_record_store']`
  - memory governance: `['mgcm_governance']`
  - model providers: `['openai', 'openai_http']`

### Size and hotspot concentration

- `agentorch/runtime/runtime.py`: `2179` lines
- `agentorch/facade.py`: `826` lines
- `agentorch/strategies.py`: `739` lines
- `agentorch/config/settings.py`: `653` lines
- `agentorch/runtime/context_kernel.py`: `413` lines
- `agentorch/runtime/context_compaction.py`: `410` lines

### Dependency structure

- Detected import cycles:
  - `evolution.session -> runtime.agent -> runtime.runtime -> evolution.session`
  - `strategies <-> runtime.context_compaction`
- Highest fan-out module: `runtime.runtime`
- Highest fan-in hotspot: `tools.base`

### Test and verification status

- Root pytest collection is now bounded to `agentorch/tests` and `tests`
- `codexharness/worktrees` no longer pollute root test collection
- Clean root collection count: `263`
- Full default suite passes: `261 passed, 2 skipped`
- Capability config precedence bug is now covered by [`tests/test_model_config_precedence.py`](../../tests/test_model_config_precedence.py)

## Severity-Ranked Findings

### 1. High: Runtime is a monolithic execution kernel instead of a narrow orchestration core

- Problem definition:
  - `Runtime` currently owns assembly, execution loop, retrieval orchestration, workflow execution, supervisor delegation, tool execution, observability setup, lifecycle cleanup, and policy normalization.
- Impact range:
  - Any feature touching reasoning, workflows, multi-agent delegation, observability, retrieval, or lifecycle risks regressions in unrelated runtime paths.
- Evidence:
  - [`agentorch/runtime/runtime.py`](../../agentorch/runtime/runtime.py) at `2179` lines
  - `Runtime.acreate`, `Runtime.__init__`, `_configure_observability`, `_register_builtin_knowledge_tools`, `_normalize_reasoning`, `_run_supervisor`, `_run_workflow`, tool execution, and `aclose()` all live in the same class.
- Why this is architectural:
  - The class is simultaneously acting as assembler, application service, execution engine, and resource container. That is a boundary problem, not a local implementation problem.
- Recommended fix direction:
  - Split `Runtime` into:
    - `RuntimeAssembler`
    - `RunExecutor`
    - `WorkflowExecutor`
    - `SupervisorExecutor`
    - `ToolExecutionService`
    - `RuntimeLifecycle`
- Breaking API impact:
  - Likely yes for internal extension points and any code instantiating or subclassing `Runtime` directly.

### 2. High: The public API surface is too wide and couples stable entry points to import-time side effects

- Problem definition:
  - Importing `agentorch` performs registry bootstrap and exposes a root API with `256` re-exports.
- Impact range:
  - Import order affects behavior, startup semantics are non-trivial, and "what is stable public API" is unclear.
- Evidence:
  - [`agentorch/__init__.py`](../../agentorch/__init__.py) exports `256` symbols and executes `bootstrap_*` calls at top level.
  - [`agentorch/models/__init__.py`](../../agentorch/models/__init__.py) registers providers during import.
- Why this is architectural:
  - This mixes package namespace definition with runtime initialization. It turns import into implicit state mutation.
- Recommended fix direction:
  - Shrink root exports to a stable API tier only.
  - Move bootstrap into explicit functions such as `agentorch.bootstrap_defaults()` or lazy registry access.
  - Move advanced and experimental exports into subpackages rather than root re-exports.
- Breaking API impact:
  - Yes. Import paths such as `from agentorch import ...` would need to be narrowed.

### 3. High: Cross-layer dependency cycles show that policy, runtime, and evolution boundaries are already leaking

- Problem definition:
  - There are real module cycles, not just conceptual coupling.
- Impact range:
  - Makes refactoring harder, encourages private-helper imports across packages, and increases the chance of partial-import or initialization bugs.
- Evidence:
  - `evolution.session -> runtime.agent -> runtime.runtime`
  - `strategies <-> runtime.context_compaction`
  - [`agentorch/evolution/session.py`](../../agentorch/evolution/session.py) imports `Agent` plus private helpers `_safe_export` and `_workflow_summary` from [`agentorch/runtime/agent.py`](../../agentorch/runtime/agent.py).
  - [`agentorch/strategies.py`](../../agentorch/strategies.py) imports runtime compaction helpers inside `DefaultContextSelector.select(...)`.
- Why this is architectural:
  - The cycle exists because schema-like and behavior-like concerns are not separated. Evolution should not need runtime debug helpers. Strategy schema should not depend on runtime compaction implementation.
- Recommended fix direction:
  - Introduce a dedicated debug/export utility module independent of runtime/agent.
  - Split policy schemas from policy executors.
  - Keep evolution summarization adapter-based, not runtime-import-based.
- Breaking API impact:
  - Mostly internal, but any direct private helper imports or custom selector implementations would be affected.

### 4. High: Config schema and environment resolution are mixed, which previously caused explicit configuration to lose against environment defaults

- Problem definition:
  - `ModelConfig` combines schema, default resolution, endpoint normalization, and sub-capability inheritance in one place.
- Impact range:
  - Configuration can become host-process dependent, especially for embedding/speech/video/image sub-capabilities.
- Evidence:
  - [`agentorch/config/settings.py`](../../agentorch/config/settings.py) owns both environment parsing and model normalization.
  - This rollout reproduced and fixed the case where explicit base `api_key` / `base_url` were being overridden by env-backed capability defaults.
- Why this is architectural:
  - Schema objects should represent validated state. They should not also be the primary policy engine for environment precedence.
- Recommended fix direction:
  - Keep `ModelConfig` as validated data.
  - Move environment lookup and precedence merging into a dedicated resolver layer, for example `ModelConfigResolver`.
  - Keep sub-capability inheritance rules explicit and centrally documented.
- Breaking API impact:
  - Likely low for ordinary callers, but medium for callers relying on undocumented env precedence.

### 5. Medium: Facade assembly is doing too much policy resolution and bookkeeping, which duplicates runtime responsibility

- Problem definition:
  - `create_agent` and `create_multi_agent` are not just convenience wrappers. They are full assembly pipelines with profile defaults, conflict enforcement, runtime-config merging, model coercion, tool normalization, and blueprint/debug binding.
- Impact range:
  - The facade becomes a second orchestration layer, and changes to runtime policy rules require synchronized updates in multiple places.
- Evidence:
  - [`agentorch/facade.py`](../../agentorch/facade.py) at `826` lines
  - [`agentorch/_facade_support.py`](../../agentorch/_facade_support.py) at `296` lines
  - `create_multi_agent(...)` recursively calls `create_agent(...)` for member assembly.
- Why this is architectural:
  - Facades should simplify entry, not become a second assembly engine parallel to the runtime.
- Recommended fix direction:
  - Move normalization and precedence logic into a single assembly service.
  - Keep facade functions thin and declarative.
  - Treat profile defaults as assembly presets, not embedded control flow in public functions.
- Breaking API impact:
  - Yes for callers depending on broad facade parameter combinations and implicit precedence.

### 6. Medium: Debug/export helpers are treated like first-class public contract instead of optional inspection tooling

- Problem definition:
  - `Agent` currently carries `export_blueprint`, `export_core_assembly`, `inspect`, and `describe`, and tests assert against those structures as if they were stable external API.
- Impact range:
  - Debug payload shape becomes sticky and expensive to change. Internal design experiments turn into compatibility constraints.
- Evidence:
  - [`agentorch/runtime/agent.py`](../../agentorch/runtime/agent.py)
  - [`tests/test_facade.py`](../../tests/test_facade.py)
  - [`agentorch/tests/test_public_api_contracts.py`](../../agentorch/tests/test_public_api_contracts.py)
- Why this is architectural:
  - Tooling/introspection surfaces are different from core execution API. Treating them equally inflates the public contract.
- Recommended fix direction:
  - Move inspection/export behavior into a separate debug or diagnostics namespace.
  - Keep `Agent` focused on execution and parsed execution.
- Breaking API impact:
  - Yes for callers using inspection helpers directly.

### 7. Medium: "Config" is not a pure configuration layer

- Problem definition:
  - `agentorch.config` re-exports policy classes and skill routing types in addition to pure config objects.
- Impact range:
  - Callers import `config` expecting plain config schemas, but actually pull in strategy and skill-layer concerns.
- Evidence:
  - [`agentorch/config/__init__.py`](../../agentorch/config/__init__.py)
- Why this is architectural:
  - The package boundary no longer means anything stable. Namespaces stop communicating layer intent.
- Recommended fix direction:
  - Restrict `agentorch.config` to data-bearing config models and config utilities only.
  - Move policy schemas to `agentorch.policy` or `agentorch.strategies.schema`.
- Breaking API impact:
  - Yes for import paths, but low implementation risk.

### 8. Medium: Test architecture was under-specified, and a diagnostic script was masquerading as a default pytest test

- Problem definition:
  - The root collection previously traversed `codexharness/worktrees`, and a root-level `test_openai_responses.py` file was not a normal pytest unit test.
- Impact range:
  - False negatives, import mismatch noise, and incorrect confidence in default CI/local test results.
- Evidence:
  - This rollout reproduced the collection pollution and then bounded default collection through [`pyproject.toml`](../../pyproject.toml).
  - `test_openai_responses.py` depends on missing pytest fixtures and behaves like an endpoint probe script.
- Why this is architectural:
  - Test boundaries are part of system architecture. If default verification scope is ambiguous, the framework has no trustworthy baseline.
- Recommended fix direction:
  - Keep root pytest scoped to primary test directories.
  - Move diagnostic probes under `scripts/` or `examples/`, or rename them away from `test_*.py`.
  - Add architecture guard tests for import graph, public API surface, and config precedence.
- Breaking API impact:
  - No runtime API impact, but test invocation expectations change.

## Target Layering Draft

### 1. Stable API layer

- Contents:
  - `Agent`
  - `Runtime`
  - `create_agent`
  - `create_multi_agent`
  - a small, deliberate set of config/policy types
- Rule:
  - no bootstrap side effects
  - no debug-helper re-exports
  - no advanced registry mutation on import

### 2. Assembly / facade layer

- Contents:
  - profile presets
  - assembly presets
  - compatibility shims
- Rule:
  - transforms user intent into a single assembly spec
  - does not execute runtime behavior directly

### 3. Execution kernel layer

- Contents:
  - run loop
  - workflow executor
  - supervisor executor
  - tool dispatch
  - lifecycle hooks
- Rule:
  - owns execution only
  - receives already-resolved config and dependencies

### 4. Policy schema layer

- Contents:
  - `ContextPolicy`
  - `StatePolicy`
  - `CoordinationPolicy`
  - `MemoryPolicy`
- Rule:
  - pure schema and defaults
  - no imports back into runtime implementation

### 5. Policy executor layer

- Contents:
  - context selector
  - route planner
  - memory evaluator
  - compaction and rerank services
- Rule:
  - consumes policy schema
  - does not define policy types

### 6. Capability adapter layer

- Contents:
  - model adapters
  - knowledge adapters
  - memory backends
  - sandbox adapters
  - tool adapters
- Rule:
  - provider-specific logic stays here
  - runtime sees normalized interfaces only

### 7. Registry / plugin layer

- Contents:
  - registries
  - registration APIs
  - explicit or lazy default bootstrap
- Rule:
  - registration happens explicitly or lazily
  - importing API namespaces should not mutate global registries

### 8. Debug / diagnostics layer

- Contents:
  - blueprint export
  - core assembly export
  - runtime description helpers
  - architecture audit helpers
- Rule:
  - separate from execution API
  - safe to change without redefining the stable runtime contract

## Refactor Priorities

### Immediate

- Keep root pytest scoped to `agentorch/tests` and `tests`
- Keep the new config precedence guard tests
- Move or rename `test_openai_responses.py` out of default pytest naming
- Stop adding new root-level public re-exports unless they belong to the stable API

### Near-term

- Split `Runtime` into assembly-neutral execution services
- Split `strategies.py` into schema and executor modules
- Move `Agent` inspection/export helpers into a diagnostics namespace
- Remove `evolution.session -> runtime.agent` dependency and private-helper reuse
- Replace import-time bootstrap with explicit or lazy registration

### Deferred

- Prune the root public API surface into stable vs advanced namespaces
- Rehome policy/config types into cleaner namespaces
- Introduce machine-checked architecture guard tests for:
  - import cycles
  - import-time bootstrap calls
  - root export count ceilings
  - configuration precedence invariants

## Implemented in This Rollout

- Added reproducible architecture metric collection script:
  - [`experiments/architecture_audit/collect_agentorch_architecture_metrics.py`](../../experiments/architecture_audit/collect_agentorch_architecture_metrics.py)
- Generated static evidence bundle:
  - [`metrics.json`](./metrics.json)
- Fixed root pytest collection boundaries in:
  - [`pyproject.toml`](../../pyproject.toml)
- Fixed explicit-base-vs-env precedence for model capability config in:
  - [`agentorch/config/settings.py`](../../agentorch/config/settings.py)
- Added regression coverage for config precedence:
  - [`tests/test_model_config_precedence.py`](../../tests/test_model_config_precedence.py)

## Final Classification

If evaluated strictly against the intended direction of "Python composition, defaults closed, single-agent and multi-agent compatible, core/extension split", `AgentTorch` is currently:

- **strong on functionality**
- **moderate on testable behavior**
- **weak on architectural separation**

It should be treated as a **working monolithic framework kernel with a large facade surface**, not yet as a clean reusable base layer.
