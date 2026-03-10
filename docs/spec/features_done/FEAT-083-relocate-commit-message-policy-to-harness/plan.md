---
plan_id: FEAT-083
feature_id: FEAT-083
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Move commit message policy module into harness
  status: done
  verification:
  - uv run python harness/fitness-functions/validate_commit_messages.py --help
- id: ST-002
  title: Update harness validator script to import policy locally
  status: done
  verification:
  - uv run python harness/fitness-functions/validate_commit_messages.py --commit-range
    HEAD~1..HEAD
- id: ST-003
  title: Update tests to cover harness commit policy entrypoint
  status: done
  verification:
  - uv run pytest -q tests/test_commit_message_validation.py
- id: ST-004
  title: Confirm harness root YAML-only rule still passes
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-005
  title: Apply reviewer cleanup to harness commit policy
  status: done
  verification:
  - uv run pytest -q tests/test_commit_message_validation.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Move commit message policy module into harness

Move `src/engineeringagent/commit_messages.py` to
`harness/fitness-functions/commit_messages.py`.

## ST-002 Update harness validator script to import policy locally

Update `harness/fitness-functions/validate_commit_messages.py` to import
from `commit_messages` in the same directory.

## ST-003 Update tests to cover harness commit policy entrypoint

Update tests that previously imported `engineeringagent.commit_messages` to
validate behavior via subprocess invocation of the harness validator script.

## ST-004 Confirm harness root YAML-only rule still passes

Ensure no new regular files were added directly under `harness/` and existing
harness rules still pass after the move.

## ST-005 Apply reviewer cleanup to harness commit policy

Incorporate small clarity/maintenance simplifications after relocating
the commit subject policy into the harness fitness-functions zone.
