---
plan_id: FEAT-063
feature_id: FEAT-063
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update implementation prompt contract for importance-first TDD execution
  status: done
  verification:
  - uv run pytest tests/test_loop_ralph_mode.py -q -k prompt
- id: ST-002
  title: Replace order-based verification command selection with done-transition detection
  status: done
  verification:
  - uv run pytest tests/test_loop_ralph_mode.py -q -k verification
- id: ST-003
  title: Remove order-sequencing and done-prefix validator invariants and relax in-progress
    subtask restriction
  status: done
  verification:
  - uv run pytest tests/test_validator.py -q
- id: ST-004
  title: Remove subtask order field from model and schema artifacts
  status: done
  verification:
  - uv run pytest tests/test_validator.py -q
- id: ST-005
  title: Migrate all active and done feature specs to remove order fields
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-006
  title: Finalize regressions for new loop and spec contracts
  status: done
  verification:
  - uv run pytest tests/test_validator.py tests/test_loop_ralph_mode.py -q
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update implementation prompt contract for importance-first TDD execution

Replace next-eligible wording with most-important-open-subtask selection and explicit red-green-refactor instructions.

## ST-002 Replace order-based verification command selection with done-transition detection

Capture pre/post subtask statuses and run verification only for subtasks that transitioned to done in the iteration.

## ST-003 Remove order-sequencing and done-prefix validator invariants and relax in-progress subtask restriction

Delete order-sequence and done-prefix checks and allow multiple in_progress subtasks in feature specs.

## ST-004 Remove subtask order field from model and schema artifacts

Update SubtaskSpec and generated feature schema so order is no longer part of the accepted contract.

## ST-005 Migrate all active and done feature specs to remove order fields

Apply a deterministic one-time migration over docs/spec/features and docs/spec/features_done.

## ST-006 Finalize regressions for new loop and spec contracts

Confirm end-to-end behavior for validator and loop runtime under the new contract.

Notes:
- Added regression coverage for done-transition verification command filtering when non-string entries appear in subtask verification payloads.
- Added prompt-contract regression requiring "most important open subtask first" wording in the implementation prompt template.
- Added regression coverage to ignore blank-string verification entries when newly done subtasks are evaluated for same-iteration verification.
- Added regression coverage to normalize surrounding whitespace on done-transition verification commands before execution/logging.
- Added prompt-contract regression requiring explicit "red -> green -> refactor" sequencing language.
- Added prompt-contract regression requiring verification instructions to state that chosen-subtask verification runs only after same-iteration transition to done.
- Added regression confirming done-transition verification ignores newly inserted done subtasks that lack a pre-implement status snapshot (stable-id diff only).
- Added regression confirming done-transition verification executes at most one verification payload per stable subtask id when duplicate ids appear in post-implement feature data.
- Added regression confirming pre-implement duplicate subtask ids use first-entry status for stable-id done-transition verification diffing.
- Added validator regression requiring AGENTS boot-sequence wording to use importance-first subtask selection language and remove legacy "next eligible subtask" phrasing.
- Updated AGENTS and harness engineering principles docs to align work-selection guidance with "most important open subtask" semantics.
- Added validator regression requiring harness engineering principles documentation to include explicit TDD loop wording (red -> green -> refactor).
