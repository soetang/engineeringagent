---
plan_id: FEAT-103
feature_id: FEAT-103
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Refactor markdown locality rule_id test to use tmp cwd
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_locality.py
- id: ST-002
  title: Consolidate loop subprocess boundary scenarios to reduce semgrep runs
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
- id: ST-003
  title: Refactor validate group execution test to use a minimal temp repo
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Verify suite speedup with durations
  status: done
  verification:
  - uv run pytest -q --durations=20
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Refactor markdown locality rule_id test to use tmp cwd

Update tests/fitness/test_fitness_rules_markdown_locality.py so the rule_id test runs the checker against tmp_path instead of repo_root to avoid full-repo scanning.

## ST-002 Consolidate loop subprocess boundary scenarios to reduce semgrep runs

Update tests/fitness/test_fitness_rules_loop_subprocess_boundary.py to collapse multiple failing scenario tests into a single test that writes multiple violating modules and asserts all expected violations from a single checker run.

## ST-003 Refactor validate group execution test to use a minimal temp repo

Update tests/checks/test_run_checks_contract.py so test_run_checks_validate_group_executes validates the execution path using tmp_path (minimal scaffold), not repo_root.

## ST-004 Verify suite speedup with durations

Run the suite with durations reporting and confirm the previously slow tests are no longer large outliers.
