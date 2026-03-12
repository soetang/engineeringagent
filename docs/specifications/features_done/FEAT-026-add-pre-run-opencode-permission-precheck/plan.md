---
plan_id: FEAT-026
feature_id: FEAT-026
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add deterministic precheck applicability logic for run mode
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_permission_precheck_applies_only_to_default_implement_mode
- id: ST-002
  title: Execute permission precheck before feature selection
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_exits_before_selection_when_permission_precheck_fails
- id: ST-003
  title: Preserve bypass behavior for skip and custom implement modes
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_skips_permission_precheck_with_skip_implement
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_skips_permission_precheck_with_custom_implement_command
- id: ST-004
  title: Remove permission probe from default loop_fast profile
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_default_loop_fast_profile_excludes_permission_probe
- id: ST-005
  title: Keep remediation guidance actionable and consistent
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_permission_precheck_failure_prints_remediation_hint
- id: ST-006
  title: Run targeted regressions and validate spec contracts
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uv run pytest -q tests/test_gates.py
  - uvx --from . engineeringagent validate --schema-only
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add deterministic precheck applicability logic for run mode

Define and centralize the decision rule for when permission precheck is required based on run flags (`--skip-implement`, `--implement-command`, default OpenCode implementer).

## ST-002 Execute permission precheck before feature selection

Insert precheck at non-dry run entry so failure exits before any feature is selected or iteration begins.

## ST-003 Preserve bypass behavior for skip and custom implement modes

Ensure `--skip-implement` and `--implement-command` paths bypass precheck and preserve their existing loop behavior.

## ST-004 Remove permission probe from default loop_fast profile

Update default gate profile configuration so permission probe is no longer part of per-iteration `loop_fast` execution.

## ST-005 Keep remediation guidance actionable and consistent

Ensure fail-fast output on precheck failure includes concrete guidance consistent with repository OpenCode permission configuration expectations.

## ST-006 Run targeted regressions and validate spec contracts

Run focused tests plus schema and loop-fast validation to confirm behavior and configuration integrity.
