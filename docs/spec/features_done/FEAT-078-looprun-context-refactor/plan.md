---
plan_id: FEAT-078
feature_id: FEAT-078
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define LoopRun, RunConfig, RunServices, RunState models (immutable + copy-on-write
    state)
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-002
  title: Refactor loop controller and iteration pipeline to pass LoopRun instead of
    many scalars
  status: done
  verification:
  - uv run pytest -q tests/test_loop_runtime_iteration.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-003
  title: Update CLI to construct LoopRun from flags and preserve run behavior
  status: done
  verification:
  - uv run python -m engineeringagent.cli run --help
  - uv run pytest -q tests/test_cli.py
- id: ST-004
  title: Update contract tests to assert the new LoopRun-based public API
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-005
  title: Add fitness rule to block facade varargs shims and hidden kwarg dropping
    regressions
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/test_gates.py
- id: ST-006
  title: Remove remaining facade shims from loop.py helpers
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-007
  title: Archive completed feature specs before done-transition verification commands
  status: done
  verification:
  - uv run pytest -q tests/test_loop_runtime_iteration.py
- id: ST-008
  title: Remove dead make_iteration_config compatibility seam from LoopRun services
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_loop_run_context_contract_immutability_and_extra_forbid
  - uv run pytest -q tests/test_loop_runtime_iteration.py::test_run_loop_controller_forwards_looprun_with_resolved_snapshot
- id: ST-009
  title: Ensure successful run archives done active specs (validate-passing)
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archives_done_active_feature_when_not_skip_implement
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archives_preexisting_done_target_after_pending_completes
- id: ST-010
  title: README - document non-dry run side effects and validate expectations
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-011
  title: README - clarify uvx vs from-source invocation vs gates/spec verification
    commands
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-012
  title: Harden facade-shim fitness rule and minor readability cleanups
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define LoopRun, RunConfig, RunServices, RunState models (immutable + copy-on-write state)

Introduce the core run context object(s) in an appropriate loop_runtime module so
dependency directionality rules remain satisfied. Ensure models are `extra=forbid`,
RunConfig/RunServices are frozen, and RunState uses copy-on-write updates.

## ST-002 Refactor loop controller and iteration pipeline to pass LoopRun instead of many scalars

Replace long parameter threading through orchestration functions with passing LoopRun.
Keep behavior equivalent (stop conditions, selection, retries, telemetry, gate/reviewer sequencing).

## ST-003 Update CLI to construct LoopRun from flags and preserve run behavior

Keep existing CLI flags and semantics, but build RunConfig from CLI args and
RunServices from the existing adapters/clients, then call the new loop entrypoint.

## ST-004 Update contract tests to assert the new LoopRun-based public API

Replace signature-stability assertions for varargs facade shims with new tests that:
- assert the LoopRun entrypoint signature
- assert immutability/copy-on-write invariants
- assert important monkeypatch seams remain available (or are replaced with equivalent seams)

## ST-005 Add fitness rule to block facade varargs shims and hidden kwarg dropping regressions

Add or extend a fitness function that scans `src/engineeringagent` and fails if:
- loop entrypoints use `*args/**kwargs` facade shims
- code assigns `__signature__ = ...` to mask varargs signatures
- code drops unexpected kwargs to bypass binding (unless explicitly allowlisted)
Register the rule in `harness/fitness-functions/rules.yaml` and ensure it runs under
existing gate profiles.

## ST-006 Remove remaining facade shims from loop.py helpers

Continue replacing facade-style `*args/**kwargs` + `__signature__` helpers in `src/engineeringagent/loop.py` (notably `_run_feature_iteration` and `print_summary`) with explicit typed contracts while preserving monkeypatch seams and CLI-visible behavior.

Notes:
- Removed `print_summary` facade varargs/signature shim.
- Replaced `_run_feature_iteration` facade varargs/signature shim with an explicit typed signature and direct `FeatureIterationInputs` construction.

## ST-007 Archive completed feature specs before done-transition verification commands

Address first-run non-dry regressions where implement marks feature/subtasks done under docs/spec/features and then subtask verification (`engineeringagent validate`) fails before archive. Ensure done features are archived before running verification commands so done-active validation does not fail the same iteration.

Notes:
- Reordered iteration phase execution so archive runs before verification.
- Added regression ensuring done-transition verification observes archived state.

## ST-008 Remove dead make_iteration_config compatibility seam from LoopRun services

Follow-up cleanup from reviewer feedback: remove the now-unused iteration-config seam from `RunServices`, simplify default service wiring, and update contract/runtime test stubs to match the reduced service contract.

Notes:
- Removed `make_iteration_config` field from `RunServices` and default loop wiring.
- Updated test stubs to construct `RunServices` without the removed seam.

## ST-009 Ensure successful run archives done active specs (validate-passing)

Fix a regression where `engineeringagent run` could return success while leaving `status: done` feature YAML files under `docs/spec/features/`, causing `engineeringagent validate` to fail immediately afterward.

Notes:
- Updated run candidate selection so done specs pending archive are processed even when `--skip-implement` is not set.
- Updated integration tests to use LoopRun-based public API.

## ST-010 README - document non-dry run side effects and validate expectations

Clarify that non-dry `engineeringagent run` can create a git commit and move completed specs from `docs/spec/features/` to `docs/spec/features_done/`. Explain that `engineeringagent validate` rejects `status: done` specs under `docs/spec/features/`.

Notes:
- README now calls out non-dry git commit + spec archival side effects.
- README now documents that validate rejects done specs under docs/spec/features.

## ST-011 README - clarify uvx vs from-source invocation vs gates/spec verification commands

Avoid onboarding confusion by explaining that gates/spec verification commands are executed from the repo (e.g. `uv run ...`) even if the CLI is invoked via `uvx engineeringagent ...`.

## ST-012 Harden facade-shim fitness rule and minor readability cleanups

Follow-up cleanup from reviewer feedback: make back-compat unused parameters explicitly unused via `del`, simplify LoopRun state forwarding in the controller, and harden the no-facade-varargs fitness rule to detect `setattr(..., name="__signature__", ...)` creative-compliance patterns.

Notes:
- Added regression test to ensure signature masking via keyword `setattr` is rejected.
- Simplified controller state forwarding and clarified unused back-compat parameter handling.
