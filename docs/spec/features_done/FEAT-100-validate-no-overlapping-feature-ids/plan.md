---
plan_id: FEAT-100
feature_id: FEAT-100
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add spec id uniqueness + filename-id alignment checks to validator
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Add TOML config support for tool.engineeringagent.specs.allow-duplicate-done-base-ids-below
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Add validator tests for collisions and remediation messaging
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Add legacy done-spec opt-out to this repo via pyproject.toml
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Refactor feature id invariant validator to satisfy ruff
  status: done
  verification:
  - uv run ruff check src/engineeringagent harness
  - uv run pytest -q
- id: ST-006
  title: Archive FEAT-100 spec to features_done
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-007
  title: Remove stdlib dataclasses from validator context models
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add spec id uniqueness + filename-id alignment checks to validator

Implement two new validations: (1) filename id token must match frontmatter id, and (2) base feature ids must be unique, with done-only legacy opt-out support.

## ST-002 Add TOML config support for tool.engineeringagent.specs.allow-duplicate-done-base-ids-below

Extend config loading to read the new specs threshold setting from engineeringagent.toml ([specs]) and pyproject.toml ([tool.engineeringagent.specs]), with deterministic precedence, and wire it into validator behavior.

## ST-003 Add validator tests for collisions and remediation messaging

Add meta tests that cover: active duplicates fail always, done duplicates fail by default, done duplicates pass when threshold opt-out applies, filename/frontmatter mismatch fails, and remediation strings include or omit the opt-out message appropriately.

## ST-004 Add legacy done-spec opt-out to this repo via pyproject.toml

This repository contains historical duplicate FEAT ids under docs/spec/features_done/. Add the following to pyproject.toml so validation remains strict for active specs while permitting old archived duplicates:
  [tool.engineeringagent.specs]
  allow-duplicate-done-base-ids-below = 100

## ST-005 Refactor feature id invariant validator to satisfy ruff

Refactor _append_feature_id_invariant_issues to reduce cyclomatic complexity and argument count without changing behavior.

## ST-006 Archive FEAT-100 spec to features_done

Completed feature specs must live under docs/spec/features_done/.

## ST-007 Remove stdlib dataclasses from validator context models

Fitness rules forbid stdlib dataclasses in src/. Replace any internal validator context dataclasses with pydantic BaseModel without changing behavior.
