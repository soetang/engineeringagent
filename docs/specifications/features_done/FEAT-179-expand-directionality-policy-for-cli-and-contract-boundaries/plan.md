---
plan_id: FEAT-179
feature_id: FEAT-179
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define explicit CLI package and contract-owner directionality boundaries
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_directionality.py
- id: ST-002
  title: Add/update deterministic tests for expanded directionality policy
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_directionality.py
- id: ST-003
  title: Sync rule docs after policy expansion
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
- id: ST-004
  title: Run final validation for boundary enforcement updates
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_directionality.py
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define explicit CLI package and contract-owner directionality boundaries

Translate the intended `src/engineeringagent/cli/` package seams and domain-owned contract ownership into concrete blocked-dependency policy entries. Prefer nested module entries such as `engineeringagent.cli.typer`/`engineeringagent.cli.main` over unsupported bare package names.

## ST-002 Add/update deterministic tests for expanded directionality policy

Extend the existing fitness-rule tests so CLI-package and contract-owner boundaries are enforced by deterministic test cases rather than implicit expectations. Add nested-module tests and reverse-direction tests for `engineeringagent.specs` versus `engineeringagent.checks.contracts`.

## ST-003 Sync rule docs after policy expansion

Refresh any generated or maintained rule documentation affected by the expanded directionality policy.

## ST-004 Run final validation for boundary enforcement updates

Confirm the stronger policy is validated, documented, and compatible with the current repository layout.
