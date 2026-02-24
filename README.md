# Engineering Agent

NOTE: This repository is under active development. You should probably not use it for anything important yet.
Treat `engineeringagent init` as experimental scaffolding and review all generated changes before committing.

Engineeringagent is a CLI that helps you implement code changes directly from feature specs.
It pairs an agent loop with repository-owned harnesses (validators, checks, fitness functions,
and optional reviewer agents).

You will still need to implement/configure the harness for your repository. If you are just
starting out, the first few specs you run should usually be harness improvements.

Primary flow: `feature spec -> run loop`.

## Command styles

- Package usage (PyPI, no clone): `uvx engineeringagent <command>`
- Package usage (version pinned): `uvx engineeringagent@<version> <command>`

## Quickstart from PyPI (no clone)

1. Make sure you are in a git repository.

   When the process starts, at least one commit will be made per implemented feature.

1. Scaffold the baseline harness with `init`.

   `init` is interactive (it requires a TTY and will prompt you with choices).

   ```bash
   uvx engineeringagent init slim
   ```

   You can also scaffold a more complete baseline:

   ```bash
   uvx engineeringagent init standard
   ```

   Warning: `init` is experimental scaffolding. Inspect generated files,
   run `uvx engineeringagent validate`, and review the git diff before committing.

1. Create a feature spec in `docs/spec/features/`.

   Use the schema `docs/spec/schemas/feature.schema.json` to create a spec.
   Save this as `docs/spec/features/FEAT-001-example.yaml`.

1. Validate and dry-run the loop first:

   ```bash
   uvx engineeringagent validate
   uvx engineeringagent run --all --dry-run
   ```

1. Dry-run the loop first:

   ```bash
   uvx engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
   ```

1. Before the first non-dry `engineeringagent run`, either commit the scaffold/spec changes or pass `--allow-dirty`.

   Running non-dry mutates your feature YAML and writes progress logs (for example `progress/runs.jsonl` and `progress/run-feature-<FEATURE_ID>.txt`).
   Running non-dry will create a commit and may include untracked files; check `git status` and commit/review any `init` scaffold output (and ignore junk like `__pycache__/`) before the first non-dry run.

   After a feature is complete, move completed specs from `docs/spec/features/` to `docs/spec/features_done/` (the loop will usually do this automatically when marking a feature `done`, but move it manually if it did not).
   `engineeringagent validate` rejects `status: done` specs under `docs/spec/features/`.

   Help validate OpenCode wiring up-front:
   - `opencode --version`
   - `.opencode/agents/engineeringagent.md`

   The first non-dry run may take a while (especially the first time, when OpenCode is cold-starting).

   By default, `engineeringagent run` retries failed iterations up to `--max-iterations` (default 50).
   When debugging OpenCode timeouts, `--max-iterations 1` helps fail fast.


## Quickstart from source (contributors / local changes)

If you are developing this repo and want to exercise local changes (not the PyPI package), install the project into your local uv environment and run the CLI via the console script:

```bash
uv sync
uv run engineeringagent init slim
uv run engineeringagent validate
uv run engineeringagent run --all --dry-run
```

### Verification (contributors)

- Run the full `iteration_end` check set declared in `harness/checks.yaml`:

  ```bash
  uv run engineeringagent checks run --phase iteration_end
  ```

- Run pylint directly (same flags as the repo gate):

  ```bash
  uv run pylint --score=n --reports=n src/engineeringagent tests harness
  ```

## Bootstrapping with `init`

If you want to use the agent in one of your repositories, you can scaffold a baseline harness with:

```bash
uvx engineeringagent init
```

`init` creates a starter structure for `docs/spec/` and `harness/checks.yaml` and handles
existing `docs/` or `AGENTS.md` through explicit conflict choices.

`engineeringagent init` skips pre-commit hook installation when `.git/` does not exist.
If you want hooks installed, run `git init` before `engineeringagent init`.

`engineeringagent init` skips pre-commit hook installation when `pre-commit` is not available.

If you install `pre-commit` after running init, you can wire the hooks with `pre-commit install`.

At a minimum, `init` scaffolds:

- `docs/spec/` directories for feature specs
- `harness/checks.yaml` as the repo-owned verification contract

It does not run checks for you or make any commits.

Warning: treat `init` as experimental scaffolding.

Always inspect generated files, run `uvx engineeringagent validate`, and review
the git diff before committing anything produced by `init`.

If you picked `standard`, the scaffold may include demo checks. Remove any demo-only
checks from `harness/checks.yaml` if you want a clean baseline (or re-run:
`uvx engineeringagent init slim --force`).

Use `python_uv` as a profile when you want the scaffolded `.pre-commit-config.yaml` to assume an
`uv`-based workflow and ship a minimal Python validation baseline.

`python_uv` also wires a `commit-msg` hook.

```bash
uvx engineeringagent init slim --scaffold-profile python_uv
```

### Pinning the scaffolded OpenCode model (optional)

`engineeringagent init` scaffolds the OpenCode agent prompt at `.opencode/agents/engineeringagent.md`.
If you want to pin which model OpenCode uses for that agent, pass `--model`:

```bash
uvx engineeringagent init slim --model openai/gpt-5.3-codex
```

If you are only validating wiring in CI (for example, smoke tests that run OpenCode once), using a
faster model can reduce wall time:

```bash
uvx engineeringagent init slim --model openai/gpt-5.3-codex-spark
```

This repository does not use the legacy repo-root OpenCode config file (the old `opencode` JSON).
Any temporary OpenCode configuration should be done via `.opencode/agents/*.md`.

## What this gives you

- Deterministic progress: one spec file at a time.
- Human control: you set priorities and scope; agents execute loops.
- Built-in quality checks: validation, checks, and commit hooks.

## Run output tips

- Default output is concise; full implement/check output stays in `progress/run-feature-<FEATURE_ID>.txt`.
- Use `--verbose-output` if you want full implement/check output in the terminal.

## OpenCode default agent contract

- By default, `engineeringagent run` shells out to `opencode run --agent engineeringagent`
   for the implementation step.
- Your repo must have OpenCode available and configured, including an agent prompt
  like `.opencode/agents/engineeringagent.md`.
- If you are not using OpenCode, run the direct verification tools for your repository (for example `uv run pytest -q`).

## Human docs vs agent docs

- `README.md`: first-run, for you the developer.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper for you the developer.
- `AGENTS.md` and `docs/references/*.md`: agent execution rules and deterministic procedures.

## Reviewer agents (optional)

- Reviewer agents are a harness-managed complement to deterministic checks.
- Reviewer checks are declared in `harness/checks.yaml` and reference prompts under `harness/reviewers/prompts/`.
- For setup and migration guidance, see [Reviewer authoring guide](docs/references/reviewer-authoring-guide.md).

## Core files to know

- `docs/spec/features/`: active feature specs (`backlog`, `in_progress`, `blocked`)
- `docs/spec/features_done/`: archived completed specs (`done`)
- `harness/checks.yaml`: repo-owned verification contract
- `progress/runs.jsonl`: append-only loop execution history

## Contributing

- Pull requests are not accepted for this repository.
- Code changes are implemented through the project agent workflow.
- If you want a new capability, open a GitHub issue with the problem, desired outcome, and constraints.
- Feature requests from issues may be promoted into a formal spec under `docs/spec/features/`.

## Go deeper

- [CLI workflow details](docs/references/workflow.md)
- Agent execution map (scaffolded by init): see `AGENTS.md` (repo root)
- [Docs architecture for agents](docs/references/documentation-practices.md)

## Curated external context

- [Harness engineering overview (OpenAI)](https://openai.com/index/harness-engineering/)
- [Ralph Loop background](https://ghuntley.com/loop/)
- [Agent loop patterns (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
