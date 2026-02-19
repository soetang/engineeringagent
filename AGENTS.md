# AGENTS.md

Agent operating guide for this repository.

Keep this file concise. Add durable references and rules, not task logs.

## 1) Mission

- Build and maintain the `engineeringagent` CLI.
- Maximize reliable throughput with minimal human attention.
- Keep each loop incremental, verifiable, and recoverable.

## 2) Operating Principles

- Humans steer, agents execute.
- Keep audience split explicit: `README.md` for human onboarding, `AGENTS.md` plus `docs/references/*-llms.md` for agent execution guidance.
- Treat API/contract changes as critical documentation work: specs and agent docs must explicitly capture old behavior, new behavior, compatibility policy, and migration scope.
- One feature focus per cycle.
- Interview before drafting a new feature spec.
- Keep each loop incremental, verifiable, and recoverable.
- Encode behavior in checks and validators, not prose alone.
- For in-repo loop execution, use source-first workspace commands (`uv run ...`), not `uvx --from . engineeringagent ...`.

## 3) System of Record (Read in this order)

1. [`AGENTS.md`](AGENTS.md) (this map)
1. [`README.md`](README.md) (human workflow and local setup)
1. Relevant docs under [`docs/`](docs/) ([`docs/references/spec-writing-llms.md`](docs/references/spec-writing-llms.md) before authoring specs; [`docs/references/docs-architecture-llms.md`](docs/references/docs-architecture-llms.md) before restructuring docs)
1. [`harness/checks.yaml`](harness/checks.yaml) (active checks and phases)
1. [`harness/fitness-functions/rules.yaml`](harness/fitness-functions/rules.yaml) (fitness rule manifest)
1. [`docs/spec/features/`](docs/spec/features/) (active feature specs and subtasks)
1. [`docs/spec/schemas/feature.schema.json`](docs/spec/schemas/feature.schema.json) (spec contract)
1. [`src/engineeringagent/`](src/engineeringagent/) (implementation)

## 4) Repository Zones

- **Code:** `src/engineeringagent/`, `harness/`
- **Agent execution state:** `docs/spec/features/`, `docs/spec/features_done/`, `progress/runs.jsonl`
- **Backlog ideas (not loop-picked):** `docs/spec/potential_features.yaml`
- **Documentation:** `docs/`

## 5) Documentation Layout Reference

- `docs/fitness-functions/`
- `docs/fitness-functions/README.md`
- `docs/fitness-functions/architecture.md`
- `docs/fitness-functions/rules.md`
- `docs/principles/harness-engineering-principles.md`
- `docs/references/docs-architecture-llms.md`
- `docs/references/workflow-llms.md`
- `docs/references/python-uv-ruff-llms.md`
- `docs/references/reviewer-agents-llms.md`
- `docs/references/spec-writing-llms.md`
- `docs/references/uv-llms.md`
- `docs/spec/features/`
- `docs/spec/features_done/*.yaml`
- `docs/spec/potential_features.yaml`
- `docs/spec/schemas/feature.schema.json`

## 6) First-Window Boot Sequence

1. Read this file, then `README.md`.
1. Check repo state: `git status`, recent commits.
1. Validate specs before coding (`engineeringagent validate`).
1. Identify active feature and most important open subtask.
1. Execute one incremental unit only.
1. Re-run listed verification commands.
1. Persist outcomes for the next context window.

## 7) Verification Quick Reference

- Validate specs: `uv run engineeringagent validate`
- Inspect init profile options: `uv run engineeringagent init --help`
- Run iteration-end checks: `uv run engineeringagent checks run --phase iteration_end`
- Run feature-done checks: `uv run engineeringagent checks run --phase feature_done`

## 8) Repo Extensions (Fill In)

- Add repository-specific architecture and policy references under `docs/references/`.
- Add stack-specific setup or runtime commands to `README.md`, not this file.
- Keep `init` guidance explicit in human docs: default `core`, optional `--scaffold-profile python_uv`.
