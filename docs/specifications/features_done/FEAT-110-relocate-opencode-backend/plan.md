---
plan_id: FEAT-110
feature_id: FEAT-110
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Move OpenCode backend package and update internal imports
  status: done
  verification:
  - uv run pytest -q
- id: ST-002
  title: Update fitness-rule allowlists/paths to new backend location
  status: done
  verification:
  - uv run pytest -q
  - uv run python harness/fitness_functions/check_agents_opencode_boundary.py
- id: ST-003
  title: Allowlist relocated OpenCode client for subprocess boundary rule
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
- id: ST-004
  title: Enforce boundary for from-import forms and remove non-agent backend imports
  status: done
  verification:
  - uv run pytest -q
  - uv run python harness/fitness_functions/check_agents_opencode_boundary.py
- id: ST-005
  title: Tighten boundary tests and guard relocated start_agent imports
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_agents_opencode_boundary.py
    tests/meta/test_agent_boundary_guards.py
  - uv run python harness/fitness_functions/check_agents_opencode_boundary.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Move OpenCode backend package and update internal imports

## ST-002 Update fitness-rule allowlists/paths to new backend location

After relocating the OpenCode backend package, update the fitness enforcement that protects the agent/opencode dependency boundary (rule_id: `architecture.agents-opencode-boundary`) so that it continues to allow imports from the new backend location under `engineeringagent/agents/backends/opencode/**` and continues to forbid direct OpenCode usage elsewhere.

## ST-003 Allowlist relocated OpenCode client for subprocess boundary rule

Relocating the OpenCode backend moved subprocess usage from the legacy `engineeringagent.opencode.client` module path to the new backend implementation under `engineeringagent.agents.backends.opencode.client`. The subprocess boundary fitness rule must treat this new module as an approved command adapter.

## ST-004 Enforce boundary for from-import forms and remove non-agent backend imports

Tighten the agents/OpenCode boundary checker so it flags `from ... import ...` imports for both legacy and backend module prefixes. Ensure production modules outside `src/engineeringagent/agents/**` no longer import backend module paths.

## ST-005 Tighten boundary tests and guard relocated start_agent imports

Address reviewer feedback: ensure boundary violation tests are fully specific (exact count) and ensure meta boundary guards catch start_agent imports from the relocated backend module paths.
