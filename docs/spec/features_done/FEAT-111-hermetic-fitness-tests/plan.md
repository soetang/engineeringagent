---
plan_id: FEAT-111
feature_id: FEAT-111
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Audit tests/fitness for repo-root scan targets and remove them
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-002
  title: Refactor repo-dependent catalog/manifest assertions to fixture-based checks
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-003
  title: Consolidate semgrep loop-subprocess-boundary scenarios to minimize startups
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
- id: ST-004
  title: Remove semgrep-backed harness script usage from generic adapter tests
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py
- id: ST-005
  title: Verify suite speed improvement with durations
  status: done
  verification:
  - uv run pytest -q --durations=20
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Audit tests/fitness for repo-root scan targets and remove them

Identify tests in `tests/fitness/**` that pass `repo_root` as the check target (directly or indirectly) and refactor them to execute against `tmp_path` fixtures instead.

## ST-002 Refactor repo-dependent catalog/manifest assertions to fixture-based checks

Replace tests that assert the real repository's catalog/manifest contents with tests that validate catalog/manifest parsing and rule registration behavior using a minimal synthetic harness fixture written under `tmp_path`.

## ST-003 Consolidate semgrep loop-subprocess-boundary scenarios to minimize startups

Update `tests/fitness/test_fitness_rules_loop_subprocess_boundary.py` so multiple violation patterns are asserted from a single checker invocation (single semgrep scan) on a single tmp fixture.

## ST-004 Remove semgrep-backed harness script usage from generic adapter tests

Ensure `tests/fitness/test_fitness_adapters.py` tests the command adapter with a fast deterministic script and does not redundantly invoke semgrep-backed checkers. Keep semgrep-backed behavior tested only in the dedicated rule test module.

## ST-005 Verify suite speed improvement with durations

Run the suite with durations and confirm that the slowest `tests/fitness/**` entries are no longer dominated by repeated semgrep startups or repo-root scans.
