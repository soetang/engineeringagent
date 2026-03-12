---
plan_id: FEAT-129
feature_id: FEAT-129
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define lightweight strategy orchestration contracts
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py -k "decision or contract"
- id: ST-002
  title: Wire FEAT-127 shared checks-config loader into run_checks entry
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
- id: ST-003
  title: Implement command and fitness strategies with deterministic planning and
    execution
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py tests/checks/test_fitness_group_port.py
    tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Implement reviewer and validate strategies with checks-owned prompt feedback
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
- id: ST-005
  title: Add checks API and CLI dry-run behavior
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
    tests/cli/test_cli.py
- id: ST-006
  title: Remove loop check-type retry feedback branching
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_runtime_iteration.py
- id: ST-007
  title: Lock determinism and first-failure invariants with regressions
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/harness/test_checks_runtime.py
- id: ST-008
  title: Run final validation and FEAT-128 overlap audit
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-009
  title: Add loop-checks boundary fitness rule
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-010
  title: Add checks-owned prompt feedback boundary fitness rule
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-011
  title: Add checks surface group discovery and normalization API
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
    tests/checks/test_checks_exports.py
- id: ST-012
  title: Update checks import-surface enforcement for new public helpers
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_checks_import_surface.py tests/checks/test_checks_exports.py
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-013
  title: Complete FEAT-129 maintainability simplifications behind boundary rules
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/loop/test_loop_phases_coverage.py
    tests/fitness/test_fitness_rules_loop_checks_result_boundary.py tests/fitness/test_fitness_rules_checks_own_prompt_feedback_rendering.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define lightweight strategy orchestration contracts

Define shared check context, decision, and execution record contracts plus strategy registration interface without adding new pydantic-only contract classes.

## ST-002 Wire FEAT-127 shared checks-config loader into run_checks entry

Use one canonical loader path for `harness/checks.yaml` load/contract/model-validation outcomes before strategy planning/execution.

## ST-003 Implement command and fitness strategies with deterministic planning and execution

Move command/fitness selection and execution orchestration behind strategy interfaces that emit stable decisions/executions and failure prompt feedback text.

## ST-004 Implement reviewer and validate strategies with checks-owned prompt feedback

Move reviewer/validate flows into strategies and ensure failing reviewer feedback is returned in prompt-ready markdown mini-block text via `prompt_feedback`.
Feedback follow-up removes duplicate reviewer planning by executing reviewer runtime from strategy-planned decisions and keeping `run_planned_reviewer_checks(...)` as a compatibility wrapper around plan-then-delegate.
Reviewer retry follow-up fixed deterministic command-invocation contract coverage by patching the command runner symbol consumed by strategy execution (`engineeringagent.checks.strategies.run_shell_command`), and made validate strategy prompt-feedback rendering explicit with `return None` for readability.

## ST-005 Add checks API and CLI dry-run behavior

Add `dry_run` option to checks API and checks CLI run command and ensure decisions-only, side-effect-free behavior with deterministic output.

## ST-006 Remove loop check-type retry feedback branching

Replace loop-side check-type payload mapping with direct forwarding of checks `prompt_feedback` string into prompt rendering.
Iteration follow-up hardened prompt rendering to accept checks-owned plain markdown retry feedback (non-envelope) without rewriting it into `retry_feedback_parse_error`.
Retry feedback follow-up now hardens gate/reviewer phase feedback forwarding to ignore blank prompt-feedback strings and preserve checks-owned plain markdown feedback verbatim so retries do not regress into synthetic `retry_feedback_parse_error` payloads.
Feedback follow-up aligned loop retry prompt regressions with checks-owned markdown feedback by asserting the forwarded `### Checks Failure` mini-block contract instead of legacy JSON envelope markers.
Reviewer retry-feedback follow-up strengthened loop-phase and integration regressions to assert deterministic sentinel forwarding identity from checks `prompt_feedback` and rejection of stale/raw check output tokens.

Reviewer feedback hardening follow-up strengthened `test_run_gate_phase_emits_fitness_failure_retry_feedback_contract` to assert exact checks-owned fitness markdown forwarding and reject raw check output tokens, and replaced one opencode retry-feedback integration path to exercise real gate `run_checks` output instead of monkeypatching `loop_runtime.phases.run_checks`.

## ST-007 Lock determinism and first-failure invariants with regressions

Add parity regressions for stable decision ordering/reasons, dry-run explainability, and stop-on-first-failure behavior.
Retry feedback follow-up normalized strategy decision `phase` fields to plain phase values (for example `iteration_end`) so deterministic decision-trace output remains contract-stable and no longer leaks enum repr tokens.

## ST-008 Run final validation and FEAT-128 overlap audit

Validated integration and completed FEAT-128 overlap audit: FEAT-129 already
owns the checks-runtime contract boundary with no remaining FEAT-128-delivered
runtime contract dependencies, so overlap is tracked as residual cleanup only.

Iteration follow-up addressed reviewer warning simplifications in checks request
typing and gate-phase failure feedback state flow before rerunning validation.

Final follow-up addressed reviewer warning simplifications by converting internal
checks orchestration state to a dataclass and extracting CLI checks-group normalization
into a dedicated helper before rerunning validation.

Retry follow-up preserved loop/checks boundary behavior for checks-owned plain
markdown prompt feedback and reran full spec validation to confirm no `retry_feedback_parse_error`
regressions are introduced while closing FEAT-129.

Feedback follow-up replaced stdlib dataclass orchestration state in checks API
with a pydantic `BaseModel` state container to satisfy `architecture.no-stdlib-dataclasses-in-src`
without changing checks strategy orchestration behavior.

Final iteration reran `uv run engineeringagent validate` after overlap audit and
passed, closing FEAT-129.

Reviewer feedback follow-up removed markdown-content assertions from loop retry
feedback tests, shifted checks contract assertions to structured decision/execution
records, and stabilized boundary fitness tests around prohibited signal identifiers
instead of full human-readable violation phrasing.

Retry feedback follow-up removed remaining loop retry assertions that depended on
exact wrapper prose in opencode and ralph integration tests and kept behavior-focused
checks on forwarding/replacement semantics plus `retry_feedback_parse_error` absence.

Reopened for reviewer feedback hardening to finish deterministic sentinel forwarding
assertions across loop retry integration coverage before final close.

Follow-up completed deterministic sentinel replacement coverage for opencode loop
retry integration so second-failure feedback replaces first-failure feedback without
leaking raw checks output tokens or `retry_feedback_parse_error` wrappers.

Validation follow-up: setting feature status to `done` before archival failed
`uv run engineeringagent validate` because completed features must live under
`docs/spec/features_done/`; keep FEAT-129 active until archival transition is
handled.

Iteration completion: reran `uv run engineeringagent validate` after finishing
FEAT-129 checks/loop boundary hardening and it passed; ST-008 is complete while
feature-level status remains `in_progress` pending archival migration to
`docs/spec/features_done/`.

Reviewer feedback follow-up simplified check-phase typing across strategy contracts,
removed duplicated loop prompt-feedback normalization via a shared helper, and made
validate strategy prompt-feedback return explicit before rerunning validation.
Feedback follow-up removed a trailing useless return in validate strategy prompt-feedback rendering to satisfy `pylint_validate` before final validation rerun.
Reviewer retry follow-up simplified internal checks orchestration state in `checks/api.py` from a private pydantic model to a lightweight mutable container, refreshed `run_checks(...)` API docstring supported kwargs to match `RunChecksKwargs`, and deduplicated repeated `--checks` CLI values at normalization time to preserve first-seen order before downstream request building.

Iteration completion follow-up reran `uv run engineeringagent validate` after closing remaining FEAT-129 feedback updates; validation passed and ST-008 is now marked done while feature archival migration remains a separate repository workflow step.

Reviewer feedback follow-up hardened gate-phase fitness retry feedback regression in `tests/loop/test_loop_phases_coverage.py` to assert deterministic checks-owned markdown forwarding identity and explicit rejection of raw check output tokens, and converted `tests/loop/test_loop_opencode_integration.py` gate retry-feedback round-trip coverage to run real checks orchestration (without monkeypatching `loop_runtime.phases.run_checks`) so one integration path validates the live checks-output to loop prompt-feedback boundary.

Retry feedback follow-up relaxed remaining FEAT-129 loop retry assertions away from exact markdown prose/layout in opencode and gate-phase coverage tests, and kept only behavioral boundary signals (checks feedback forwarded, gate identity/remediation preserved, raw output excluded, no `retry_feedback_parse_error`) before rerunning validation.

Reviewer feedback follow-up replaced remaining loop integration monkeypatches of `loop_runtime.phases.run_checks` in opencode/ralph retry-feedback flows with real temporary `harness/checks.yaml` command-check execution, and kept assertions focused on true checks->loop prompt-feedback forwarding/replacement semantics while rejecting raw check output leakage and `retry_feedback_parse_error` wrappers.

Iteration bookkeeping follow-up transitioned ST-008 to `done` after rerunning `uv run engineeringagent validate`; feature status remains `in_progress` until archival migration to `docs/spec/features_done/`.

Feedback follow-up simplified checks request kwargs validation reuse, consolidated reviewer decision normalization in reviewers runtime, and ignored blank plain-text retry feedback during prompt injection before validation rerun.

Validation bookkeeping follow-up re-opened ST-008 while this completed feature spec remains under `docs/spec/features/`; archival migration to `docs/spec/features_done/` is required before final `status: done` can validate.

Iteration step: transitioned ST-008 back to `done` and reran `uv run engineeringagent validate`; validation required archival migration for completed features.

Archival completion step: moved FEAT-129 spec to `docs/spec/features_done/`, kept feature `status: done`, and reran `uv run engineeringagent validate` to confirm the feature now satisfies completed-spec placement rules.

Reopened for code_simplifier retry feedback to remove an unused strategy plan parameter and fix reviewer prompt wording before rerunning validation.

Validation follow-up: reran `uv run engineeringagent validate`, reconciled status bookkeeping (`all subtasks done => feature status done`), and prepared for final validation rerun.

Iteration bookkeeping follow-up: validation requires completed specs to be archived under `docs/spec/features_done/`; keep FEAT-129 active in `docs/spec/features/` by reopening ST-008 until archival migration is executed as a dedicated workflow step.

Reviewer prompt wording follow-up: clarified and corrected wording in `harness/reviewers/prompts/code_simplifier.md` fitness-function guidance for deterministic reviewer instruction quality before the next archival/validation pass.

Incremental step: removed CLI `checks run` failure runtime-type reporting dependency on `failed_group` by deriving check type from strategy-owned decision/execution records, and added regression coverage that preserves runtime failure labeling when `failed_group` is absent from the checks result contract.

Incremental step: removed `failed_group` from the `ChecksRunResult` API contract and orchestration failure returns so checks results stay loop-facing and strategy-neutral, and updated checks/CLI regressions to assert failure identity via `failed_check_id` plus decision/execution records instead of group labels.

Validation follow-up: transitioned ST-008 to done and ran `uv run engineeringagent validate`; validator still requires `status: done` when all subtasks are done, so ST-008 is re-opened pending dedicated archival/status workflow handling.

Incremental step: transitioned ST-008 and FEAT-129 to `done` together to satisfy all-subtasks-done status invariants before rerunning validation in this iteration.

Pylint feedback follow-up removed a trailing useless return in validate strategy prompt-feedback rendering (`pylint R1711`) before final validation rerun.

Validation status follow-up aligned feature status to `done` after all subtasks were complete so spec validation can pass in-place.

Validation bookkeeping follow-up re-opened ST-008 and feature status because completed features must be archived under `docs/spec/features_done/` before final `status: done` can validate.

Incremental step: tightened loop retry feedback fallback to keep checks-owned prompt feedback as the only forwarded failure text, with a deterministic generic fallback when checks provide blank feedback, and added gate-phase regression coverage that rejects raw check output forwarding when prompt feedback is missing.

Incremental simplification step: removed duplicate loop prompt-feedback normalization before `_checks_retry_feedback(...)` so gate/reviewer failure flows keep the same checks-owned feedback contract with less orchestration branching surface.

## ST-009 Add loop-checks boundary fitness rule

Add `architecture.loop-checks-result-boundary` to fail when loop runtime branches on check type/group semantics or parses checks-internal payload contracts.

## ST-010 Add checks-owned prompt feedback boundary fitness rule

Add `architecture.checks-own-prompt-feedback-rendering` to fail when loop/prompt code performs check-type-specific retry feedback shaping outside checks strategies.

## ST-011 Add checks surface group discovery and normalization API

Adopt an agents-registry-style stable checks selection surface for non-checks modules by exporting helpers from `engineeringagent.checks` (for example, `list_check_groups()` and `normalize_check_groups(...)`) that wrap `request_normalization` internals.
Use this top-level checks surface in CLI and remove direct checks-submodule imports while preserving trim/validate/dedupe/order behavior.

## ST-012 Update checks import-surface enforcement for new public helpers

Expand `architecture.checks-import-surface` allowlist to include newly approved top-level checks helper exports while keeping submodule imports forbidden outside checks internals.
Update fitness/export tests and docs references so the supported checks surface remains explicit and deterministic.

## ST-013 Complete FEAT-129 maintainability simplifications behind boundary rules

Finish remaining code_simplifier maintainability follow-ups using the strict checks surface:
- shared prompt-feedback normalization helper reused by checks API and loop runtime, - shared planner-to-decision mapping helper in checks strategies, - centralized `ChecksRunResult` finalization helper in checks API, and - shared AST/file-scope traversal helper used by the two FEAT-129 boundary fitness scripts.
