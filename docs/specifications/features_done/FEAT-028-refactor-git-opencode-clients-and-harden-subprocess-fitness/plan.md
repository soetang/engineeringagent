---
plan_id: FEAT-028
feature_id: FEAT-028
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add explicit OpenCode and Git client submodules
  status: done
  verification:
  - uv run pytest -q tests/test_opencode_client.py
  - uv run pytest -q tests/test_git_client.py
- id: ST-002
  title: Refactor loop orchestration to use command clients
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uv run pytest -q tests/test_gates.py::test_default_loop_fast_profile_excludes_permission_probe
- id: ST-003
  title: Harden subprocess boundary rule with strict allowlist and alias detection
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_loop_subprocess_boundary.py
  - uv run pytest -q tests/test_fitness_registry.py
- id: ST-004
  title: Surface remediation guidance in fitness run output and retry feedback
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_fitness_run_json_includes_remediation_for_failures
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_includes_fitness_remediation_guidance
- id: ST-005
  title: Update built-in subprocess rule remediation and generated catalog
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uv run pytest -q tests/test_fitness_catalog_generation.py
- id: ST-006
  title: Run focused regressions and validate contracts
  status: done
  verification:
  - uvx --from . engineeringagent validate --schema-only
  - uv run pytest -q tests/test_cli.py
  - uv run pytest -q tests/test_gates.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add explicit OpenCode and Git client submodules

Create orchestration-focused command clients inside dedicated package directories (src/engineeringagent/opencode/ and src/engineeringagent/git/) that encapsulate low-level command details and return deterministic process outputs.

## ST-002 Refactor loop orchestration to use command clients

Route loop feature selection, implement execution, worktree checks, completion commit, and permission probe command paths through the new clients and remove generic bypass wrappers.

## ST-003 Harden subprocess boundary rule with strict allowlist and alias detection

Enforce allowlisted subprocess-using modules and detect alias/import-based subprocess usage so wrapper indirection cannot bypass architecture intent.

## ST-004 Surface remediation guidance in fitness run output and retry feedback

Expose metadata remediation text for failing rules in fitness CLI output so gate failure payloads include clear "what to do instead" guidance.

## ST-005 Update built-in subprocess rule remediation and generated catalog

Revise built-in subprocess boundary remediation text to reference the new client package modules and regenerate docs/fitness-functions/rules.md.

## ST-006 Run focused regressions and validate contracts

Confirm schema validity and no regressions in loop execution, gate behavior, and fitness enforcement after the refactor.
