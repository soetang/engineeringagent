---
plan_id: FEAT-101
feature_id: FEAT-101
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add test reviewer prompt file
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-002
  title: Wire test reviewer into harness checks
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-003
  title: Add tests for reviewer prompt/config
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Fix markdown locality violation in harness templates
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add test reviewer prompt file

Create harness/reviewers/prompts/test_reviewer.md containing the prompt text in implementation_notes, including the $responseformat placeholder.

## ST-002 Wire test reviewer into harness checks

Add a new reviewer entry in harness/checks.yaml referencing the prompt file, running at feature_done, and scoped to tests/**/*.py at minimum.

## ST-003 Add tests for reviewer prompt/config

Add/extend tests to ensure the reviewer prompt exists, includes $responseformat, and is registered in harness/checks.yaml under type: reviewer.

## ST-004 Fix markdown locality violation in harness templates

Ensure fitness rules pass by avoiding markdown files outside approved locality roots (move/rename test-only templates as needed).
