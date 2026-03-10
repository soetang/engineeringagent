---
plan_id: FEAT-052
feature_id: FEAT-052
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add scaffolded readme_process reviewer entry and prompt file template
  status: done
  verification:
  - uv run pytest -q tests/test_init_scaffold.py
- id: ST-002
  title: Add runtime planner filters for feature_done and README on-change scope
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_readme_process_plans_only_for_readme_change_on_feature_done
- id: ST-003
  title: Enforce temp worktree snapshot sandbox for readme_process execution
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_readme_process_uses_temp_worktree_snapshot
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_readme_process_runs_readme_bootstrap_in_fresh_temp_directory
- id: ST-004
  title: Wire blocking retry and exhaustion behavior for readme_process
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_readme_process_request_changes_blocks_until_retry_or_exhaustion
  - uv run pytest -q tests/test_loop_reviewers.py::test_readme_process_feedback_classifies_readme_vs_init_fix_surface
  - uv run pytest -q tests/test_loop_reviewers.py::test_readme_process_exhaustion_continues_with_warning_by_default
- id: ST-005
  title: Add docs section with exact readme_process sample and plain-English semantics
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
- id: ST-006
  title: Run reviewer-specific regression slice
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_reviewers_sandbox.py
    tests/test_loop_reviewers.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add scaffolded readme_process reviewer entry and prompt file template

Add default reviewer example plus prompt artifact for readme_process in scaffold output, including explicit clean-room README bootstrap instructions.

## ST-002 Add runtime planner filters for feature_done and README on-change scope

Ensure planner only schedules readme_process when required phase and file-change criteria match.

## ST-003 Enforce temp worktree snapshot sandbox for readme_process execution

Implement and verify isolated sandbox execution path for readme_process, including running README bootstrap flow in fresh temp directory context.

## ST-004 Wire blocking retry and exhaustion behavior for readme_process

Ensure request_changes outcomes map to blocking retry flow, include README-vs-init remediation classification, and preserve default exhausted continuation warning behavior.

## ST-005 Add docs section with exact readme_process sample and plain-English semantics

Document readme_process behavior, trigger logic, and policy outcomes with exact copy-paste YAML.

## ST-006 Run reviewer-specific regression slice

Validate planner, sandbox, and loop behavior for readme_process scenario end to end.
