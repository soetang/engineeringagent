---
plan_id: FEAT-093
feature_id: FEAT-093
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove doc-content tests in reviewer reference docs module
  status: done
  verification:
  - uv run pytest -q
- id: ST-002
  title: Harden no-doc-content-tests fitness rule to catch wrapper helper calls
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/fitness
- id: ST-003
  title: Fix ruff/isort import ordering in new fitness rule tests
  status: done
  verification:
  - uv run ruff check tests/fitness/test_fitness_rules_no_doc_content_tests.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove doc-content tests in reviewer reference docs module

Delete `tests/test_reviewer_reference_docs.py` (preferred) or remove its tests.
Ensure no other tests depend on it.

## ST-002 Harden no-doc-content-tests fitness rule to catch wrapper helper calls

Update `harness/fitness_functions/check_no_doc_content_tests.py` to detect
calls like `_read(repo_root, "docs/..." )` (function name agnostic) and emit
violations for banned markdown targets.

## ST-003 Fix ruff/isort import ordering in new fitness rule tests

Align stdlib import ordering in `tests/fitness/test_fitness_rules_no_doc_content_tests.py`
to satisfy ruff/isort.
