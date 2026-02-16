# Engineering Workflow for LLMs

This reference describes the expected loop workflow for agent execution.

## Core Loop

1. Select one eligible feature and one eligible subtask.
1. Implement one incremental, deterministic unit.
1. Run the subtask verification commands.
1. Update the feature YAML status and `updated_at`.
1. Persist outcomes for the next loop.

## Verification Baseline

- Primary verification flow: `engineeringagent run --all` (consumes `harness/checks.yaml`).
- Optional spec-only validation: `engineeringagent validate`.

## Loop outcome taxonomy

The run loop records a deterministic `next_action` in terminal output and in `progress/runs.jsonl`.

- `continue_same_feature`: iteration result is `passed`, but the feature is not completed yet (keep working).
- `retry_same_feature`: iteration result is `failed` (fix and try again).
- `select_next_feature`: completion commit succeeded and the loop should move to the next eligible feature.
- `stop`: dry-run or no-work terminal states.

## Scope Boundaries

- Keep implementation edits in code and configuration, not in run logs.
- Keep repository-specific architecture decisions in repo docs, not generic references.
- Keep docs concise and link to references instead of duplicating large guidance blocks.
