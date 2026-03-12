---
plan_id: FEAT-158
feature_id: FEAT-158
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Inventory Semgrep-backed active rules
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_registry.py
- id: ST-002
  title: Implement native subprocess-boundary enforcement and policy parser
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
- id: ST-003
  title: Migrate any additional discovered Semgrep-backed active rules
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-004
  title: Remove Semgrep dependency and update active docs/manifest wiring
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q tests/fitness/test_fitness_registry.py tests/fitness/test_fitness_adapters.py
- id: ST-005
  title: Verify parity strength and runtime improvement
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
    --durations=5
  - uv run pytest -q --durations=20
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Inventory Semgrep-backed active rules

Confirm all active Semgrep-backed rule dependencies and list migration targets.

## ST-002 Implement native subprocess-boundary enforcement and policy parser

Replace Semgrep execution with native AST-based detection and load policy from native YAML allowlist config.

## ST-003 Migrate any additional discovered Semgrep-backed active rules

If ST-001 discovers additional active Semgrep-backed rules, migrate each to native checker enforcement with preserved rule ids and deterministic envelopes.

## ST-004 Remove Semgrep dependency and update active docs/manifest wiring

Remove Semgrep dependency and update active docs/manifest policy references to native enforcement contracts.

## ST-005 Verify parity strength and runtime improvement

Prove non-weakening parity with targeted pass/fail/error tests and capture before/after durations that show reduced subprocess-boundary overhead.
