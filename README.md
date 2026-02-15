# Engineering Agent

NOTE: This repository is under active development. Treat `engineeringagent init` as
experimental scaffolding and review all generated changes before committing.

Engineeringagent is a CLI that helps you implement code changes directly from feature specs.
It pairs an agent loop with repository-owned harnesses (validators, gates, fitness functions,
and optional reviewer agents).

You will still need to implement/configure the harness for your repository. If you are just
starting out, the first few specs you run should usually be harness improvements.

Primary flow: `feature spec -> run loop`.

## Command styles

- Package usage (PyPI, no clone): `uvx engineeringagent <command>`
- Package usage (version pinned): `uvx engineeringagent@<version> <command>`
- From source (this repo clone): `uv run python -m engineeringagent.cli <command>`

## Quickstart from PyPI (no clone)

1. Make sure you are in a git repository.

   `engineeringagent run` (non-dry) requires a git repo and, by default, a clean
   worktree.

   ```bash
   git init
   git status
   ```

   If you must run with local changes, pass `--allow-dirty`.

1. (Optional) Scaffold a baseline harness.

   ```bash
   uvx engineeringagent init
   ```

   Warning: `init` is experimental scaffolding. Inspect generated files,
   run `uvx engineeringagent validate`, and review the git diff before committing.

   We recommend you do this in a separate branch or toy project the first time you try out the process.

1. Create or pick one feature spec in `docs/spec/features/`.

   Save this as `docs/spec/features/FEAT-001-example.yaml`.
   Minimal example that satisfies `docs/spec/schemas/feature.schema.json`:

   ```yaml
   id: FEAT-001
   title: Example feature spec
   type: chore
   expected_commit_subject: 'chore: example feature spec'
   status: backlog
   priority: low
   objective: 'Provide a minimal, schema-valid feature spec for onboarding.'
   acceptance:
   - 'Spec validates with `engineeringagent validate`.'
   subtasks:
   - id: ST-001
     title: Validate specs
     status: backlog
     context: null
     verification:
     - engineeringagent validate
   updated_at: '2026-02-15T00:00:00Z'
   ```

1. Validate the setup and run gates.

   ```bash
   uvx engineeringagent validate
   uvx engineeringagent gates run --profile loop_fast
   ```

1. Do a safe dry run first.

   ```bash
   uvx engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
   ```

1. Run for real by removing `--dry-run`.

   If you do not have OpenCode installed/configured, either:

   - pass `--implement-command <cmd>` to run your own implementation command, or
   - pass `--skip-implement` to only run gates.

## Bootstrapping a new repository with `init`

If you are starting in a fresh repository, you can scaffold a baseline harness with:

```bash
uvx engineeringagent init
```

`init` defaults to the language-agnostic `core` scaffold profile.

Use `python_uv` when you want the scaffolded `.pre-commit-config.yaml` to assume an
`uv`-based workflow (including a commit-msg hook); it does not add gate definitions
to `harness/gates.yaml`.

```bash
uvx engineeringagent init --scaffold-profile python_uv
```

`init` creates a starter structure for `docs/spec/` and `harness/gates.yaml` and handles
existing `docs/` or `AGENTS.md` through explicit conflict choices.

At a minimum, `init` scaffolds:

- `docs/spec/` directories for feature specs
- `harness/gates.yaml` as a starting point for your gate profiles

It does not run gates for you or make any commits.

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

## OpenCode default agent contract

- By default, `engineeringagent run` shells out to `opencode build-agent run` for the
  implementation step.
- Your repo must have OpenCode available and configured, including an agent prompt
  like `.opencode/agents/engineeringagent.md`.
- If you are not using OpenCode, use `--implement-command <cmd>` (or `--skip-implement`).

## Human docs vs agent docs

- `README.md`: first-run, for you the developer.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper for you the developer.
- `AGENTS.md` and `docs/references/*-llms.md`: agent execution rules and deterministic procedures.

## Reviewer agents (optional)

- Reviewer agents are a harness-managed complement to deterministic gates, configured in `harness/reviewers.yaml`.
- `engineeringagent init` does not scaffold reviewer config or prompts; keep reviewer policy repository-owned through committed harness files.
- Use `uvx engineeringagent reviewers init` to scaffold a baseline config and prompt files under `harness/reviewers/prompts/`.
- Use `uvx engineeringagent reviewers list|plan|run` to inspect and test reviewer behavior.
- For setup and migration guidance, see [Reviewer authoring guide](docs/principles/reviewer-authoring-guide.md).
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
- [Agent execution map (scaffolded by init)](AGENTS.md)
- [Docs architecture for agents](docs/references/docs-architecture-llms.md)

## Curated external context

- [Harness engineering overview (OpenAI)](https://openai.com/index/harness-engineering/)
- [Ralph Loop background](https://ghuntley.com/loop/)
- [Agent loop patterns (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
