# Engineering Workflow for LLMs

This reference describes the expected loop workflow for agent execution.

## Core Loop

1. Select one eligible feature and one eligible subtask.
1. Implement one incremental, deterministic unit.
1. Run the subtask verification commands.
1. Update the feature YAML status and `updated_at`.
1. Persist outcomes for the next loop.

## Verification Baseline

- Validate specs and layout: `engineeringagent validate`.
- Inspect configured gates: `engineeringagent gates list`.
- Run required gates: `engineeringagent gates run --profile precommit`.

## Scope Boundaries

- Keep implementation edits in code and configuration, not in run logs.
- Keep repository-specific architecture decisions in repo docs, not generic references.
- Keep docs concise and link to references instead of duplicating large guidance blocks.
