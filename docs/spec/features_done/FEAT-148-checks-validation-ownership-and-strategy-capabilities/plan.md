---
plan_id: FEAT-148
feature_id: FEAT-148
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add validator contracts and deterministic registry
  status: done
  verification:
  - uv run pytest -q tests/checks
- id: ST-002
  title: Extract repo-global validators from monolithic validate module
  status: done
  verification:
  - uv run pytest -q tests/checks tests/specs
- id: ST-003
  title: Implement reviewer strategy-owned static validator
  status: done
  verification:
  - uv run pytest -q tests/reviewers tests/checks
- id: ST-004
  title: Implement fitness strategy-owned static validator
  status: done
  verification:
  - uv run pytest -q tests/fitness tests/checks
- id: ST-005
  title: Wire validate entrypoint to composed validator registry and preserve deterministic
    output
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q tests/checks
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add validator contracts and deterministic registry

Introduce shared validation models/protocols and enforce deterministic ordering and duplicate-registration rejection.

## ST-002 Extract repo-global validators from monolithic validate module

Move cross-cutting repository policies into focused repo validator modules while preserving behavior.

## ST-003 Implement reviewer strategy-owned static validator

Move reviewer prompt static policy checks into reviewer-owned validation path.

## ST-004 Implement fitness strategy-owned static validator

Move fitness catalog and manifest static policy checks into fitness-owned validation path.

## ST-005 Wire validate entrypoint to composed validator registry and preserve deterministic output

Keep one `engineeringagent validate` command surface while routing execution through the new ownership model.
