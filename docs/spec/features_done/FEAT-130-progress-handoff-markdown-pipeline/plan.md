---
plan_id: FEAT-130
feature_id: FEAT-130
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Refactor progress path topology helpers to feature-scoped layout
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_state.py tests/meta/test_progress_import_paths.py
- id: ST-002
  title: Migrate runtime progress writes and references to new paths
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    -k "progress or log_path"
- id: ST-003
  title: Add structured handoff contract to implementation prompt
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py -k "prompt"
- id: ST-004
  title: Add structured handoff envelope model and markdown append renderer helpers
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py -k "handoff"
- id: ST-005
  title: Wire handoff append into loop observer/telemetry publish flow
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    -k "handoff or progress"
- id: ST-006
  title: Add manual progress CLI helper commands for append and feature cleanup
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_checks.py -k "progress"
- id: ST-007
  title: Update gitignore and docs for new progress artifact layout
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-008
  title: Update progress locality fitness implementation for new canonical paths
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
- id: ST-009
  title: Run final integration and contract validation sweep
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-010
  title: Simplify implement-step result typing and output coercion
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-011
  title: Re-run final FEAT-130 integration sweep and archive spec
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-012
  title: Apply post-review cleanup for legacy ignore entries and handoff template
    casing
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-013
  title: Archive FEAT-130 spec under features_done
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-014
  title: Apply reviewer simplification feedback for CLI feature-id handling and implement
    output_type capability detection
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-015
  title: Fix prompt contract wording regression for hand-off phrase
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py -k "prompt_includes_feature_file_path"
  - uv run engineeringagent validate
- id: ST-016
  title: Reduce FEAT-130 handoff tests to stable behavior assertions
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    -k "handoff"
  - uv run engineeringagent validate
- id: ST-017
  title: Run final FEAT-130 completion sweep and archive spec
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-018
  title: Apply code-simplifier readability cleanup in FEAT-130 touched modules
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-019
  title: Re-run FEAT-130 completion sweep and archive spec when remaining feedback
    closes
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-020
  title: Address follow-up code-simplifier feedback on timestamp/helper readability
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-021
  title: Re-run FEAT-130 completion sweep and archive spec after latest cleanup
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-022
  title: Apply follow-up code-simplifier dedupe cleanup in telemetry and implement
    success output
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-023
  title: Restore telemetry now_iso shim for deterministic test monkeypatching
  status: done
  verification:
  - uv run pytest -q
  - uv run engineeringagent validate
- id: ST-024
  title: Refocus FEAT-130 retry tests on public handoff behavior
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_contracts.py
    -k "handoff or implement_step"
  - uv run engineeringagent validate
- id: ST-025
  title: Remove remaining brittle markdown-shape assertions from FEAT-130 handoff
    tests
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py -k "handoff"
  - uv run engineeringagent validate
- id: ST-026
  title: Re-run completion sweep and archive FEAT-130 spec after retry feedback settles
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-027
  title: Apply final reviewer readability cleanups in implement imports and prune
    output
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-028
  title: Re-run FEAT-130 completion sweep and archive spec after ST-027
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
    tests/reviewers/test_reviewers_state.py tests/reviewers/test_reviewers_state_cache.py
    tests/meta/test_progress_import_paths.py tests/cli/test_cli.py tests/cli/test_cli_checks.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run engineeringagent validate
- id: ST-029
  title: Apply follow-up code-simplifier dedupe cleanup in progress path references
    and implement artifact setup
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Refactor progress path topology helpers to feature-scoped layout

Implement canonical path helpers for runs, feature directories, run log, handoff markdown, and reviewer state under the new folder structure.

## ST-002 Migrate runtime progress writes and references to new paths

Update implement/telemetry/helpers call sites to use only centralized new path helpers and ensure references emitted in output payloads are correct.

## ST-003 Add structured handoff contract to implementation prompt

Update prompt template and prompt coverage tests so implement prompt references the feature handoff markdown file for prior-context reading and explicitly says to write the hand-off so that the next developer can easily continue the work; keep wording deterministic for tests.

## ST-004 Add structured handoff envelope model and markdown append renderer helpers

Introduce progress handoff helper module and typed envelope model for `ImplementProgressEnvelope`, then append normalized Markdown entries with deterministic fallback when structured validation fails.

## ST-005 Wire handoff append into loop observer/telemetry publish flow

Integrate handoff append once per iteration in loop-owned runtime flow, preserving deterministic ordering and append-only semantics.

## ST-006 Add manual progress CLI helper commands for append and feature cleanup

Add CLI subcommands for operator-driven handoff append from stdin and feature-scoped manual cleanup; keep retention policy manual-only.

## ST-007 Update gitignore and docs for new progress artifact layout

Migrate documentation and ignore rules to reference and protect the new progress directory hierarchy and handoff markdown artifact.

## ST-008 Update progress locality fitness implementation for new canonical paths

Keep `architecture.progress-log-path-locality` effective by updating approved literals/helper names and any rule logic that depends on old path tokens.

## ST-009 Run final integration and contract validation sweep

Re-run targeted tests plus full spec/fitness validation to confirm path migration, prompt contract, and handoff append behavior are stable.

## ST-010 Simplify implement-step result typing and output coercion

Address reviewer simplification feedback by consolidating implement-step result tuple typing into a named alias, normalizing return shape at the implement boundary, simplifying string-output coercion control flow, and removing the now-unneeded feature-id argument from fixed run-log filename helper.

## ST-011 Re-run final FEAT-130 integration sweep and archive spec

After incremental cleanup iterations, run the full FEAT-130 verification sweep and archive this feature spec under docs/spec/features_done when complete.

## ST-012 Apply post-review cleanup for legacy ignore entries and handoff template casing

Address follow-up reviewer feedback by removing stale immediate-break legacy `.gitignore` entries and normalizing handoff template placeholder casing to `<FEATURE_ID>` for consistency.

## ST-013 Archive FEAT-130 spec under features_done

After final confirmation, move this completed spec file to `docs/spec/features_done/` to satisfy completed-spec archival policy.

## ST-014 Apply reviewer simplification feedback for CLI feature-id handling and implement output_type capability detection

Address reviewer follow-up by deduplicating progress CLI feature-id input validation, replacing brittle exception-message matching in implement output_type fallback logic with explicit signature inspection, and correcting prompt-template wording for feedback/handoff phrasing consistency.

## ST-015 Fix prompt contract wording regression for hand-off phrase

Address retry feedback from `pytest_validate` by restoring the exact prompt contract sentence: "Write the hand-off so that the next developer can easily continue the work." in the implementation prompt template.

## ST-016 Reduce FEAT-130 handoff tests to stable behavior assertions

Address reviewer feedback by removing markdown prose/section coupling from FEAT-130 handoff tests and keeping assertions focused on append occurrence, fallback state signaling, and feature-scoped artifact creation.

## ST-017 Run final FEAT-130 completion sweep and archive spec

After retry-feedback fixes land, run the full FEAT-130 acceptance verification set and archive the spec under docs/spec/features_done when complete.

## ST-018 Apply code-simplifier readability cleanup in FEAT-130 touched modules

Address reviewer follow-up simplification feedback by reducing duplication in implement output coercion and markdown handoff section rendering while preserving deterministic FEAT-130 behavior.

## ST-019 Re-run FEAT-130 completion sweep and archive spec when remaining feedback closes

Keep one final completion step open so full acceptance verification and features_done archival happen only after all reviewer feedback cycles are fully settled.

## ST-020 Address follow-up code-simplifier feedback on timestamp/helper readability

Apply the remaining readability simplifications requested by reviewer feedback: reuse shared UTC timestamp helper in implement-step progress logging and flatten progress handoff append stdin JSON parsing with a helper.

## ST-021 Re-run FEAT-130 completion sweep and archive spec after latest cleanup

Keep final completion/archive work explicitly open after ST-020 so the repo-level completion sweep and docs/spec/features_done archival happen in a dedicated final iteration.

## ST-022 Apply follow-up code-simplifier dedupe cleanup in telemetry and implement success output

Address latest reviewer feedback by removing duplicate timestamp formatter in loop telemetry payload writes and extracting repeated implement success command-output formatting into a shared helper.

## ST-023 Restore telemetry now_iso shim for deterministic test monkeypatching

Address retry feedback from `pytest_validate` by restoring a module-level `now_iso()` shim in loop telemetry and using it for run payload timestamps so timing tests can monkeypatch deterministic timestamps without reaching into progress helpers.

## ST-024 Refocus FEAT-130 retry tests on public handoff behavior

Address follow-up `test_reviewer` feedback by removing monkeypatched helper-call interception in handoff telemetry tests and dropping direct private-helper assertions so coverage stays behavior-oriented and resilient.

## ST-025 Remove remaining brittle markdown-shape assertions from FEAT-130 handoff tests

Address `test_reviewer` retry feedback by dropping handoff markdown heading/content assertions from loop output tests and keeping coverage focused on path creation and append-growth behavior.

## ST-026 Re-run completion sweep and archive FEAT-130 spec after retry feedback settles

Keep one final closeout task open so full acceptance verification and docs/spec/features_done archival occur only after the latest retry-fix iteration is reviewed.

## ST-027 Apply final reviewer readability cleanups in implement imports and prune output

Address remaining code_simplifier retry feedback by unifying implement-step handoff imports through the `progress_handoff` namespace and reusing a single computed feature-prune relative path in CLI output branches.

## ST-028 Re-run FEAT-130 completion sweep and archive spec after ST-027

Keep feature closeout explicit after this retry-feedback cleanup so completion sweep plus docs/spec/features_done archival occur in a dedicated follow-up iteration.

## ST-029 Apply follow-up code-simplifier dedupe cleanup in progress path references and implement artifact setup

Address latest code_simplifier retry feedback by introducing a shared repo-relative path formatter for progress reference helpers and removing redundant progress root directory creation in implement artifact setup while preserving behavior.
