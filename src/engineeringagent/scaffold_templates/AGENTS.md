# AGENTS.md

Agent operating guide for this repository.

Keep this file concise. Add durable references and rules, not task logs.

## Mission

- Build and maintain a reliable engineering loop with minimal human attention.

## Operating Principles

- Humans steer, agents execute.
- Keep audience split explicit: `README.md` for human onboarding, `AGENTS.md` plus `docs/references/*-llms.md` for agent execution guidance.
- One feature focus per cycle.
- Keep each loop incremental, verifiable, and recoverable.

## System of Record (Read in this order)

1. `AGENTS.md` (this map)
1. `README.md` (workflow and local setup)
1. `harness/gates.yaml` (active gate profiles and commands)
1. `docs/spec/features/` (active feature specs)
1. `src/` (implementation)

## Documentation Layout Reference

- `docs/references/docs-architecture-llms.md`: Use when adding or restructuring docs; keeps human vs agent doc placement deterministic.
- `docs/references/workflow-llms.md`: Use before running loop work; defines the expected execution and verification loop.
- `docs/references/spec-writing-llms.md`: Use when drafting feature specs; defines the feature schema expectations and the expected red-green-refactor loop.

Note: Some repos use a separate docs root for specs (configured via `engineeringagent.toml`). These reference docs remain under `docs/references/`.

## First-Window Boot Sequence

- Ensure `harness/gates.yaml` exists and profiles reference valid gates.
- Keep `docs/spec/` directories present for active, done, and backlog specs.
- Select one eligible feature/subtask before editing.
- Execute one incremental unit and record outcomes.

## Verification Quick Reference

- Validate feature schema and file structure: `engineeringagent validate`.
- List configured gate profiles: `engineeringagent gates list`.
- Execute a gate profile: `engineeringagent gates run --profile precommit`.

## Repo Extensions (Fill In)

- Add repository-specific architecture references under `docs/references/`.
- Add stack-specific setup/run commands in `README.md`, not in this file.
