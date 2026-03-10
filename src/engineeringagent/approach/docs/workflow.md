---
approach_id: workflow
---

# Engineering Workflow Reference

This reference describes the expected workflow for implementing a feature with engineeringagent.

## Create one or more specs:
- Create a spec using [specifications](specifications.md).

## Core Loop

Run the loop with: `uv run engineeringagent run --all`

1. Select one eligible feature and one eligible plan phase.
1. Implement one incremental, deterministic unit.
1. Run the current plan-phase verification commands.
1. Update the bundled feature package status surfaces (`plan.md` when present, always `spec.yaml`) and `updated_at`.
1. Persist outcomes for the next loop.

## Verification Baseline

- Primary verification flow: `uv run engineeringagent checks run --all-phases` (consumes `harness/checks.yaml`).
- Optional spec-only validation: `uv run engineeringagent validate --schema-only`.

## Loop outcome taxonomy

The run loop records a deterministic `next_action` in terminal output and in
`.engineeringagent/progress/runs/runs.jsonl`.

Runtime progress artifacts are only created on first non-dry write (a dry-run run does not create `.engineeringagent/progress/...` files).

- `continue_same_feature`: iteration result is `passed`, but the feature is not completed yet (keep working).
- `retry_same_feature`: iteration result is `failed` (fix and try again).
- `select_next_feature`: completion commit succeeded and the loop should move to the next eligible feature.
- `stop`: dry-run or no-work terminal states.
