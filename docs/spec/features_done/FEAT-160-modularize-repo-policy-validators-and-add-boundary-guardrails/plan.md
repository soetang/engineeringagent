---
plan_id: FEAT-160
feature_id: FEAT-160
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add characterization tests for repo message projection
  status: done
  verification:
  - uv run pytest -q tests/checks/test_validate_entrypoint_registry.py
- id: ST-002
  title: Extract feature-id invariants from repo_validators
  status: done
  verification:
  - uv run pytest -q tests/checks/test_validate_entrypoint_registry.py
- id: ST-003
  title: Extract docs-map and purge-invariant policy modules
  status: done
  verification:
  - uv run pytest -q tests/checks/test_validate_entrypoint_registry.py
- id: ST-004
  title: Add repo validators boundary fitness rule
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_repo_validators_boundary.py
- id: ST-005
  title: Final validation and docs sync
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add characterization tests for repo message projection

Add table-driven tests that lock message ordering and deterministic issue-code mapping behavior for repo validation message projection.

## ST-002 Extract feature-id invariants from repo_validators

Move feature-id duplicate/alignment logic to a focused module and preserve existing deterministic behavior through characterization tests.

## ST-003 Extract docs-map and purge-invariant policy modules

Move AGENTS docs-map validation and purge invariant scanning into dedicated modules and keep orchestrator behavior deterministic.

## ST-004 Add repo validators boundary fitness rule

Add a focused fitness rule that prevents monolithic regression by enforcing orchestrator-boundary constraints for repo validators.

## ST-005 Final validation and docs sync

Run repository validation and ensure fitness catalog documentation is in sync after rule additions.
