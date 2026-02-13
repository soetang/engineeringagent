# Engineering Agent

EngineeringAgent is a human-guided harness for running reliable coding loops with an agent.

Primary flow: `application spec -> run loop`

## Getting started (first 10 minutes)

1. Install dependencies.

   ```bash
   uv sync
   ```

1. Create or pick one feature spec in `docs/spec/features/`.

1. Validate the setup and run gates.

   ```bash
   uvx --from . engineeringagent validate
   uvx --from . engineeringagent gates run --profile loop_fast
   ```

1. Do a safe dry run first.

   ```bash
   uvx --from . engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
   ```

1. Run for real by removing `--dry-run`.

## Bootstrapping a new repository with `init`

If you are starting in a fresh repository, you can scaffold a baseline harness with:

```bash
uvx --from . engineeringagent init
```

`init` defaults to the language-agnostic `core` scaffold profile.
Use `python_uv` only when you intentionally want Python/uv-oriented bootstrap defaults:

```bash
uvx --from . engineeringagent init --scaffold-profile python_uv
```

`init` creates a starter structure for docs/specs/gates and handles existing `docs/` or
`AGENTS.md` through explicit conflict choices.

Warning: treat `init` as experimental scaffolding.
Always inspect generated files, run `uvx --from . engineeringagent validate`, and review
the git diff before committing anything produced by `init`.

## What this gives you

- Deterministic progress: one spec file at a time.
- Human control: you set priorities and scope; agents execute loops.
- Built-in quality checks: validation, gates, and commit hooks.

## Run output tips

- Default output is concise; full implement/gate output stays in `progress/run-feature-<FEATURE_ID>.txt`.
- Use `--verbose-output` if you want full implement/gate output in the terminal.
- TTY terminals show light styling for scanability; redirected output stays ANSI-free.
- Set `NO_COLOR=1` (or `TERM=dumb`) to force plain output.

## Human docs vs agent docs

- `README.md`: first-run, human onboarding.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper human context.
- `AGENTS.md` and `docs/references/*-llms.md`: agent execution rules and deterministic procedures.

## Core files to know

- `docs/spec/features/`: active feature specs (`backlog`, `in_progress`, `blocked`)
- `docs/spec/features_done/`: archived completed specs (`done`)
- `docs/spec/schemas/feature.schema.json`: feature schema contract
- `harness/gates.yaml`: gate and profile definitions
- `progress/runs.jsonl`: append-only loop execution history

## Contributing

- Pull requests are not accepted for this repository.
- Code changes are implemented through the project agent workflow.
- If you want a new capability, open a GitHub issue with the problem, desired outcome, and constraints.
- Feature requests from issues may be promoted into a formal spec under `docs/spec/features/`.

## Go deeper

- [CLI workflow details](docs/references/uv-llms.md)
- [Agent execution map](AGENTS.md)
- [Docs architecture for agents](docs/references/docs-architecture-llms.md)

## Curated external context

- [Harness engineering overview (OpenAI)](https://openai.com/index/harness-engineering/)
- [Ralph Loop background](https://ghuntley.com/loop/)
- [Agent loop patterns (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
