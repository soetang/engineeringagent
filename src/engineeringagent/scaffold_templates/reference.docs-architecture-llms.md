# Documentation Architecture for LLMs

This reference defines where to put human-facing and agent-facing documentation in this repository.

## Audience Split

- Human docs are for onboarding, setup, and fast understanding.
- Agent docs are for deterministic execution, constraints, and verification.
- Keep audience boundaries explicit and avoid mixing both in a single file.

## Ownership and Placement

- `README.md`: primary human onboarding and workflow overview.
- `AGENTS.md`: primary agent routing map and execution contract.
- `docs/references/*-llms.md`: agent-oriented references for stable procedures.
- `docs/spec/features/*.yaml`: loop-scoped feature and subtask execution plans.

## Authoring Expectations for Agents

- Keep changes minimal and scoped to the active feature/subtask.
- Prefer ordered steps and executable verification commands.
- Encode repeatable behavior in validators and gates when possible.
- Link from `AGENTS.md` when adding a new reference document.
