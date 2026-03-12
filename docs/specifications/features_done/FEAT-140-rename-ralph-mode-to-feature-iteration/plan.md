---
plan_id: FEAT-140
feature_id: FEAT-140
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Rename loop-topic test module and identifiers to feature_iteration
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_feature_iteration.py
- id: ST-002
  title: Update meta/layout references to renamed loop-topic test module
  status: done
  verification:
  - uv run pytest -q tests/meta/test_test_layout_loop_topic.py
- id: ST-003
  title: Update active feature spec verification commands to renamed test path
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-004
  title: Run targeted regression suite and validate naming migration
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_feature_iteration.py tests/loop/test_loop_contracts.py
    tests/loop/test_loop_opencode_integration.py tests/meta/test_test_layout_loop_topic.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Rename loop-topic test module and identifiers to feature_iteration

Rename the legacy loop-topic test module and update in-file test names/fixtures/messages that encode legacy `ralph_mode` wording while preserving test behavior.

## ST-002 Update meta/layout references to renamed loop-topic test module

Update meta tests and any active test-path assertions that reference legacy loop-topic module naming so repository layout contracts remain accurate.

## ST-003 Update active feature spec verification commands to renamed test path

Replace legacy loop-topic test module path references in active feature specs under `docs/spec/features/*.yaml` with the new `test_loop_feature_iteration.py` path.

## ST-004 Run targeted regression suite and validate naming migration

Confirm rename coherence across loop tests and integration-adjacent contracts without broad behavior drift.
