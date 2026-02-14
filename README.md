# Engineering Agent

EngineeringAgent is a human-guided harness for running reliable coding loops with an agent.

Primary flow: `application spec -> run loop`

## Command styles

- Package usage (PyPI, no clone): `uvx engineeringagent <command>`
- Package usage (version pinned): `uvx engineeringagent@<version> <command>`

## Quickstart from PyPI (no clone)

1. If you are starting in a fresh repository, scaffold the baseline harness first.

   ```bash
   uvx engineeringagent init 
   ```

   Warning: `init` is experimental scaffolding. Inspect generated files,
   run `uvx engineeringagent validate`, and review the git diff before committing.

   We recommend u do this in a seperat branch or toy project the first time you try out the process.

1. Create or pick one feature spec in `docs/spec/features/`.

1. Validate the setup and run gates.

   ```bash
   uvx engineeringagent validate
   uvx engineeringagent gates run --profile loop_fast
   ```

1. Do a safe dry run first.

   ```bash
   uvx engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
   ```

Run for real by removing `--dry-run`.

## Bootstrapping a new repository with `init`

If you are starting in a fresh repository, you can scaffold a baseline harness with:

```bash
uvx engineeringagent init
```

`init` defaults to the language-agnostic `core` scaffold profile.
Use `python_uv` only when you intentionally want Python/uv-oriented bootstrap defaults:

```bash
uvx engineeringagent init --scaffold-profile python_uv
```

`init` creates a starter structure for docs/specs/gates and handles existing `docs/` or
`AGENTS.md` through explicit conflict choices.

Warning: treat `init` as experimental scaffolding.
Always inspect generated files, run `uvx engineeringagent validate`, and review
the git diff before committing anything produced by `init`.

## What this gives you

- Deterministic progress: one spec file at a time.
- Human control: you set priorities and scope; agents execute loops.
- Built-in quality checks: validation, gates, and commit hooks.

## Run output tips

- Default output is concise; full implement/gate output stays in `progress/run-feature-<FEATURE_ID>.txt`.
- Use `--verbose-output` if you want full implement/gate output in the terminal.

## Human docs vs agent docs

- `README.md`: first-run, human onboarding.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper human context.
- `AGENTS.md` and `docs/references/*-llms.md`: agent execution rules and deterministic procedures.

## Reviewer agents (optional)

- Reviewer agents are a harness-managed complement to deterministic gates, configured in `harness/reviewers.yaml`.
- Use `uvx engineeringagent reviewers init` to scaffold a baseline config and prompt files under `harness/reviewers/prompts/`.
- Use `uvx engineeringagent reviewers list|plan|run` to inspect and test reviewer behavior.
- For full contract, policy semantics, decision-envelope examples, and troubleshooting, see [Reviewer agents reference](docs/references/reviewer-agents-llms.md).

## Core files to know

- `docs/spec/features/`: active feature specs (`backlog`, `in_progress`, `blocked`)
- `docs/spec/features_done/`: archived completed specs (`done`)
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
