---
plan_id: FEAT-170
feature_id: FEAT-170
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add init config writer support for codex profile persistence
  status: done
  verification:
  - uv run pytest -q tests/config/test_config_agents_backend.py
- id: ST-002
  title: Implement interactive conflict handling for existing codex profile values
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-003
  title: Update init tests for codex profile persistence behavior
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
  - uv run pytest -q tests/config/test_config_agents_backend.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add init config writer support for codex profile persistence

Extend init config write flow to upsert `[agents.codex].profile = "engineeringagent"`
when selected backend is codex, without introducing model persistence.

## ST-002 Implement interactive conflict handling for existing codex profile values

Add/initiate prompt behavior for existing `[agents.codex].profile` conflicts
in interactive mode and define deterministic non-interactive behavior.

## ST-003 Update init tests for codex profile persistence behavior

Adjust existing codex init assertions and add coverage for non-codex and no-model
persistence expectations.
