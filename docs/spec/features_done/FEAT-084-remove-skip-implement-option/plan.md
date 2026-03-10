---
plan_id: FEAT-084
feature_id: FEAT-084
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove run CLI flag and parsing/wiring for skip-implement
  status: done
  verification:
  - uv run python -m engineeringagent.cli run --help
  - uv run pytest -q tests/test_cli.py
- id: ST-005
  title: Add migration and breakage assertions
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_repo_readme_process_reviewer_activation.py
- id: ST-006
  title: Run full regression and enforce search invariants
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
  - uv run python -c "import subprocess,sys; from pathlib import Path; needles=(b'--skip-implement',b'skip_implement');
    allow='docs/spec/features/FEAT-084-remove-skip-implement-option.yaml'; files=subprocess.check_output(['git','ls-files'],
    text=True).splitlines(); hits=sorted([f for f in files if f!=allow and not f.startswith('docs/spec/features_done/')
    and (((data := Path(f).read_bytes()) or True) and any(n in data for n in needles))]);
    print('\\n'.join(hits)); sys.exit(1 if hits else 0)"
- id: ST-007
  title: Remove skip-implement guidance from README and reference docs
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/test_reviewer_reference_docs.py tests/test_repo_readme_process_reviewer_activation.py
- id: ST-008
  title: Remove skip-implement hints and implement-phase messaging
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_opencode_integration.py
- id: ST-009
  title: Remove skip_implement from loop config and iteration inputs
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py tests/test_loop_reviewers.py tests/test_loop_output.py
- id: ST-010
  title: Remove skip_implement behavioral branches from loop runtime
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py tests/test_loop_opencode_integration.py
- id: ST-011
  title: Remove or rewrite skip-implement focused tests
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_init_command.py tests/test_loop_ralph_mode.py
    tests/test_loop_opencode_integration.py
- id: ST-012
  title: Create early progress artifacts for non-dry run
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_creates_progress_artifacts_before_implement_invocation
- id: ST-013
  title: Clarify OpenCode preflight and first non-dry run expectations in README
  status: done
  verification:
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py
- id: ST-014
  title: Add implement-phase timeout and surface actionable errors
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-015
  title: Reduce implement-step command string duplication
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py tests/test_loop_opencode_integration.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove run CLI flag and parsing/wiring for skip-implement

Remove the `--skip-implement` option from `src/engineeringagent/cli.py` and
eliminate argument plumbing in command dispatch and loop entrypoints.

## ST-005 Add migration and breakage assertions

Add/adjust tests to lock in migration behavior:
unknown-option failure for `--skip-implement`, and docs/examples that route
users to `gates run` or `--dry-run`.

## ST-006 Run full regression and enforce search invariants

Run full test/validation and verify active code/docs no longer reference
`--skip-implement` or `skip_implement` (excluding archived specs). Exclude this spec file itself from the invariant search.

## ST-007 Remove skip-implement guidance from README and reference docs

Purge active documentation references to skip-implement and replace guidance
with `engineeringagent gates run` and/or `engineeringagent run --dry-run`.
Known active files (non-archived) include `README.md` and `docs/references/uv-workflow.md`.

## ST-008 Remove skip-implement hints and implement-phase messaging

Remove any terminal hints, help text, or runtime messaging that recommends
`--skip-implement` (for example in `src/engineeringagent/loop_runtime/implement.py`).
Ensure replacement messaging points to `engineeringagent gates run` / `--dry-run`.

## ST-009 Remove skip_implement from loop config and iteration inputs

Delete the `skip_implement` field/parameter from run-loop config models and
iteration inputs (for example `src/engineeringagent/loop.py`, loop runtime controller, and any dataclasses/typed models). Update all call sites and tests.

## ST-010 Remove skip_implement behavioral branches from loop runtime

Delete any conditional behavior keyed on skip_implement (permission precheck
bypass, advisory followup gating, one-iteration exit behavior, archive-on-done behavior, etc). After removal, `run` always follows the normal loop semantics (except `--dry-run`).

## ST-011 Remove or rewrite skip-implement focused tests

Update or remove tests that explicitly exercise skip-implement mode behavior.
Known active test files include `tests/test_loop_ralph_mode.py`, `tests/test_loop_opencode_integration.py`, and `tests/test_init_command.py`.
Preserve tests for the new unknown-option failure for `--skip-implement` and for `gates run` / `--dry-run` guidance.

## ST-012 Create early progress artifacts for non-dry run

Ensure non-dry implement writes progress/ artifacts before OpenCode starts so runs are observable even if OpenCode is slow.

## ST-013 Clarify OpenCode preflight and first non-dry run expectations in README

Document what OpenCode installed/configured means (with a concrete preflight check) plus expected first-run latency and where to observe logs/output.

## ST-014 Add implement-phase timeout and surface actionable errors

Add a bounded timeout around the OpenCode invocation and emit actionable remediation so constrained environments do not appear to hang indefinitely.

## ST-015 Reduce implement-step command string duplication

Extract a tiny helper for the opencode run command line used in implement-step outputs and simplify the timeout handling branch for clarity.
