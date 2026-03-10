---
plan_id: FEAT-058
feature_id: FEAT-058
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add Semgrep dependency and local rule scaffold
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_manifest_contract.py
- id: ST-002
  title: Implement Semgrep-to-fitness adapter script
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_adapters.py
- id: ST-003
  title: Wire pilot command rule in fitness manifest
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_registry.py tests/test_fitness_rule_id_collisions.py
- id: ST-004
  title: Prove parity with existing loop subprocess boundary behavior
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_loop_subprocess_boundary.py
- id: ST-005
  title: Run full verification bar for Semgrep pilot
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run python -m engineeringagent.cli gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add Semgrep dependency and local rule scaffold

Add semgrep to dev dependency group and create initial local rule file for subprocess-boundary patterns.

## ST-002 Implement Semgrep-to-fitness adapter script

Create deterministic mapper from semgrep output to fitness envelope with stable sorted violations.

## ST-003 Wire pilot command rule in fitness manifest

Register Semgrep command adapter rule and ensure rule id and severity remain policy-compatible.

## ST-004 Prove parity with existing loop subprocess boundary behavior

Port or adapt existing boundary rule scenarios to assert equivalent pass/fail outcomes through the pilot.

## ST-005 Run full verification bar for Semgrep pilot

Confirm repo validation and fitness runs remain stable after pilot wiring.
