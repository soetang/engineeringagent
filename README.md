# Engineering Agent

Human-guided harness for running repeatable coding loops with an agent.

## Quick start: ship one feature

Primary flow: `application spec -> run loop`

1. Write an application feature spec in `docs/spec/features/`.
1. Run validation and gates.
1. Run the loop on that spec until it is complete.

```bash
uv sync
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates run --profile loop_fast
uvx --from . engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
```

When you are ready for a real pass, remove `--dry-run`.

Default run-loop output is concise: `engineeringagent run ...` prints lifecycle status lines and keeps raw implement/gate output in `progress/run-feature-<FEATURE_ID>.txt`.
Use `--verbose-output` when you want full implement and gate output streamed in the terminal while the same detailed per-feature log is still written under `progress/`.

## What this repo is for

- Keep feature work deterministic through one spec file at a time.
- Let humans steer priorities while agents execute implementation loops.
- Preserve quality with explicit validation, gate profiles, and commit hooks.

## How to work with agents and specs

- Use specs to define what to build and how progress is verified.
- Use agents to implement harness and feature changes from those specs.
- Keep user-facing onboarding in `README.md`; keep agent execution rules in `AGENTS.md` and `docs/references/*-llms.md`.

## Core files to know

- `docs/spec/features/` active feature specs (`backlog`, `in_progress`, `blocked`)
- `docs/spec/features_done/` archived completed specs (`done`)
- `docs/spec/schemas/feature.schema.json` feature schema contract
- `harness/gates.yaml` gate and profile definitions
- `progress/runs.jsonl` append-only loop execution history

## Go deeper

- CLI workflow details: `docs/references/uv-llms.md`
- Agent execution map: `AGENTS.md`
- Docs architecture for agents: `docs/references/docs-architecture-llms.md`

## Curated external context

- Harness engineering overview: https://openai.com/index/harness-engineering/
- Agent loop patterns: https://www.anthropic.com/engineering/building-effective-agents
- Specification writing motivation: https://martinfowler.com/articles/feature-toggles.html
