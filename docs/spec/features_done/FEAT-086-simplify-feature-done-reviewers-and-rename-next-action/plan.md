---
plan_id: FEAT-086
feature_id: FEAT-086
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update reviewers.yaml contract to remove approval.mode and enforce approve/request_changes
    outcomes
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/reviewers/test_reviewers_contract.py
- id: ST-002
  title: Remove reviewer_advisory_followup behavior and advisory-followup state tracking
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_reviewers.py
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
- id: ST-008
  title: Enforce repository-wide removal of advisory vs blocking artifacts
  status: done
  verification:
  - uv run python -c "import subprocess,sys; from pathlib import Path; needles=(b'approval.mode',b'passed:advisory',b'reviewer_advisory_followup',b'blocking_exhausted',b'continue_on_exhausted',b'advisory_followup_required');
    allow='docs/spec/features/FEAT-086-simplify-feature-done-reviewers-and-rename-next-action.yaml';
    files=subprocess.check_output(['git','ls-files'], text=True).splitlines(); hits=sorted([f
    for f in files if f!=allow and not f.startswith('docs/spec/features_done/') and
    (((p := Path(f)).exists()) and (((data := p.read_bytes()) or True) and any(n in
    data for n in needles)))]); print('\\n'.join(hits)); sys.exit(1 if hits else 0)"
- id: ST-003
  title: Rename next_action values and compute them deterministically from final iteration
    state
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
  - uv run pytest -q tests/loop/test_loop_contracts.py
- id: ST-004
  title: Update terminal output, progress logs, and JSONL telemetry for renamed next_action
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py
- id: ST-005
  title: Update integration tests and fixtures asserting reviewer outcomes and next_action
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_opencode_integration.py
- id: ST-006
  title: Update docs/references for new reviewer semantics and next_action taxonomy
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/test_reviewer_reference_docs.py
- id: ST-007
  title: Run full regression and validate end-to-end loop contract
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
- id: ST-009
  title: Cleanup dead reviewer/next_action control-flow after FEAT-086
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_reviewers.py
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update reviewers.yaml contract to remove approval.mode and enforce approve/request_changes outcomes

Tighten the reviewers.yaml contract/model so `approval.mode` is removed.
Ensure that at phase=feature_done, reviewers can only effectively return approve
or request_changes. Decide whether other decisions are normalized to
request_changes (preferred for robustness) or rejected as invalid output during
parsing.

## ST-002 Remove reviewer_advisory_followup behavior and advisory-followup state tracking

Delete the reviewer_advisory_followup failure path and any related
persisted state keys (e.g. advisory_followup_required). Ensure request_changes
still blocks completion and forwards feedback via hook_feedback for the next
implement pass.

## ST-008 Enforce repository-wide removal of advisory vs blocking artifacts

Enforce that no active (non-archived) files reference advisory/blocking
mode artifacts, including approval.mode and legacy reviewer status/gate strings.
Exclude archived specs under docs/spec/features_done and exclude this spec file
itself from the invariant search.

## ST-003 Rename next_action values and compute them deterministically from final iteration state

Introduce next_action=continue_same_feature for passed continuation and
reserve retry_same_feature for failures. Update loop runtime models, iteration
pipeline, and any places that default next_action. Ensure next_action is derived
from (result, completed, completion_commit_succeeded).

## ST-004 Update terminal output, progress logs, and JSONL telemetry for renamed next_action

Update terminal summary printing and telemetry/progress logging to emit
renamed next_action values. Optionally emit next_action_legacy mapping
continue_same_feature -> retry_same_feature for a transition window.

## ST-005 Update integration tests and fixtures asserting reviewer outcomes and next_action

Update opencode integration tests and any other tests/fixtures that assert
reviewer status strings, failed gate names (reviewer_advisory_followup), or
next_action values.

## ST-006 Update docs/references for new reviewer semantics and next_action taxonomy

Update docs that describe reviewers.yaml fields and reviewer behavior so
they present reviewers as they work after this change.
Do not mention legacy reviewer modes or follow-up behavior; describe only the
supported reviewer decisions (approve/request_changes).

## ST-007 Run full regression and validate end-to-end loop contract

Run full test suite and spec validation to ensure loop output, telemetry,
and reviewer enforcement remain consistent and stable after the contract change.

## ST-009 Cleanup dead reviewer/next_action control-flow after FEAT-086

Remove redundant branches/vars that became dead after reviewers were limited
to phase=feature_done and next_action was renamed. No behavior change; this is
maintenance work to reduce future confusion.
