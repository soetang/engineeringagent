---
plan_id: FEAT-157
feature_id: FEAT-157
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Backfill legacy done metadata fields
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-002
  title: Cascade-renumber archived duplicate done IDs
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-003
  title: Remove legacy validator exceptions and threshold config support
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py tests/cli/test_cli.py
- id: ST-004
  title: Remove repo config/test references to duplicate-id opt-out
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py tests/cli/test_cli.py
- id: ST-005
  title: Final validation and contract lock-in
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Backfill legacy done metadata fields

Add missing `type` and `expected_commit_subject` fields to archived specs that predate the current contract, using the repository-approved generic placeholder subject.

## ST-002 Cascade-renumber archived duplicate done IDs

Remove archived duplicate base IDs via deterministic cascade renumbering of later done specs while preserving rough historical order and avoiding active ID collisions; rename filenames and frontmatter IDs together.

## ST-003 Remove legacy validator exceptions and threshold config support

Delete done-spec legacy required-field filtering and done duplicate threshold opt-out behavior, including config readers and remediation messaging.

## ST-004 Remove repo config/test references to duplicate-id opt-out

Remove `allow-duplicate-done-base-ids-below` from repository config files, fixtures, and assertions that currently reference the transitional policy.

## ST-005 Final validation and contract lock-in

Run strict validator and schema checks to confirm all transitional behavior is removed and migrated data remains contract-compliant.
