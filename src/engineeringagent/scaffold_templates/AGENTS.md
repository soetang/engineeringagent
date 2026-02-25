# AGENTS.md

Agent operating guide for this repository.

Keep this file concise. Add durable references and rules, not task logs.

## Mission

- Build and maintain a reliable engineering loop with minimal human attention.

## Operating Principles

- Humans steer, agents execute.
- Keep audience split explicit: `README.md` for package users, `AGENTS.md` plus `docs/references/*.md` for package contributors.
- One feature focus per cycle.
- Keep each loop incremental, verifiable, and recoverable.

## System of Record (Read in this order)

1. `AGENTS.md` (this map)
1. `README.md` (workflow and local setup)
1. `harness/checks.yaml` (repo-owned verification contract)
1. `docs/spec/features/` (active feature specs)
1. `src/` (implementation)

## Documentation Layout Reference

- `docs/references/workflow.md`: Use before running loop work; defines the expected execution and verification loop.
- `docs/references/spec-writing.md`: Use when drafting feature specs; defines feature schema expectations and the expected red-green-refactor loop.
- `docs/references/quality-check-playbook.md`: Use when selecting checks and deciding where to enforce behavior.
- `docs/references/reviewer-authoring-guide.md`: Use when adding or updating repository reviewer checks and prompts.
- `docs/references/contributor-commands.md`: Use for canonical contributor command references while iterating on this repository.
- `docs/references/documentation-practices.md`: Use when adding or restructuring docs; defines user vs contributor documentation boundaries.
- `docs/principles/harness-engineering-principles.md`: Use for conceptual rationale behind short-loop execution design.

Note: Some repos use a separate docs root for specs (configured via `engineeringagent.toml`). These reference docs remain under `docs/references/`.

## First-Window Boot Sequence

- Ensure `harness/checks.yaml` exists and validates.
- Keep `docs/spec/` directories present for active, done, and backlog specs.
- Select one eligible feature/subtask before editing.
- Execute one incremental unit and record outcomes.

## Verification Quick Reference

- Validate feature schema and file structure: `engineeringagent validate`.
- Run the engineering loop: `engineeringagent run --all`.

## Repo Extensions (Fill In)

- Add repository-specific architecture references under `docs/architecture/`.
- Add stack-specific setup/run commands in `README.md`, not in this file.
