---
plan_id: FEAT-014
feature_id: FEAT-014
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add explicit allow-dirty flag for run loop restart
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_requires_clean_worktree_by_default
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_allows_uncommitted_changes_with_allow_dirty
  - uvx --from . engineeringagent run --help
- id: ST-002
  title: Add loop archive-path resolution and safe move helper
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_moves_completed_feature_to_features_done
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archives_only_selected_feature
- id: ST-003
  title: Integrate archive move into single completion commit with retry safety
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_completion_commit_includes_archive_move
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_commit_failure_preserves_retryable_feature_path
- id: ST-004
  title: Add validator rule for done specs in active feature directory
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_reports_done_feature_left_in_active_directory
  - uv run pytest -q tests/test_validator.py::test_validate_transitional_policy_for_preexisting_done_features
- id: ST-005
  title: Document automatic archive contract and migration expectations
  status: done
  verification:
  - python3 -c "from pathlib import Path; docs=['README.md','AGENTS.md']; t='\n'.join(Path(p).read_text(encoding='utf-8').lower()
    for p in docs); assert 'features_done' in t and 'archive' in t and 'done' in t;
    print('ok')"
  - python3 -c "from pathlib import Path; docs=['README.md','AGENTS.md']; t='\n'.join(Path(p).read_text(encoding='utf-8').lower()
    for p in docs); assert '--allow-dirty' not in t or 'uncommitted' in t; print('ok')"
  - uvx --from . engineeringagent validate
- id: ST-006
  title: Run focused loop and validator regression coverage
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_validator.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add explicit allow-dirty flag for run loop restart

Extend CLI/run wiring so uncommitted changes remain blocked by default but can be explicitly allowed for restart workflows with a dedicated flag and clear runtime messaging.

## ST-002 Add loop archive-path resolution and safe move helper

Define deterministic path handling for moving a completed selected feature spec into `docs/spec/features_done/` while preserving filename and ensuring destination directory readiness.

## ST-003 Integrate archive move into single completion commit with retry safety

Wire archive behavior into completion flow so status updates and file move are committed together, and ensure failed completion commits can retry the same feature without path-loss or inconsistent state, including allow-dirty restart scenarios.

## ST-004 Add validator rule for done specs in active feature directory

Update validation checks so `status: done` specs in `docs/spec/features/` produce actionable errors, with an explicit transitional policy for preexisting done specs that are intentionally not auto-migrated by loop startup behavior.

## ST-005 Document automatic archive contract and migration expectations

Update repository docs so contributors understand that active features are pending execution scope and completed features are automatically archived by the loop, including guidance for manual cleanup of historical done specs. Add allow-dirty documentation only when the flag is implemented, and describe it using uncommitted code changes terminology.

## ST-006 Run focused loop and validator regression coverage

Execute targeted regression checks to confirm allow-dirty restart behavior, archive-on-completion behavior, and active-spec validation contract all hold under expected loop scenarios.
