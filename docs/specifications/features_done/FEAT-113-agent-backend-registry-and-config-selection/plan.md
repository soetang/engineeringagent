---
plan_id: FEAT-113
feature_id: FEAT-113
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add backend-id config resolver (backend-agnostic)
  status: done
  verification:
  - uv run pytest -q tests/config
- id: ST-002
  title: Implement backend registry mapping in engineeringagent.agents
  status: done
  verification:
  - uv run python -c "from engineeringagent import agents; print(agents.list_backends())"
  - uv run pytest -q
- id: ST-003
  title: Update run_agent to select default backend via registry + config
  status: done
  verification:
  - uv run pytest -q tests/agents
  - uv run pytest -q
- id: ST-004
  title: Add focused tests for config-driven default backend selection
  status: done
  verification:
  - uv run pytest -q tests/agents tests/config
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add backend-id config resolver (backend-agnostic)

Add a new resolver in `engineeringagent.config` that reads `[agents] backend`.
The resolver must not embed any concrete backend id string.

## ST-002 Implement backend registry mapping in engineeringagent.agents

Introduce a registry that maps backend ids to backend factories, including
OpenCode.

## ST-003 Update run_agent to select default backend via registry + config

## ST-004 Add focused tests for config-driven default backend selection

Add tests that:
- write an engineeringagent.toml selecting a backend id
- verify run_agent chooses that backend when backend=None (use a test double
  by monkeypatching the registry mapping)
- verify unknown backend id produces a deterministic error
