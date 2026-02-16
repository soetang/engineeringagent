# Engineering Agent

NOTE: This repository is under active development. And you should probably not run it locally for now.

Engineeringagent is a CLI that helps you implement code changes directly from feature specs.
It pairs an agent loop with repository-owned harnesses (validators, gates, fitness functions,
and optional reviewer agents).

You will still need to implement/configure the harness for your repository. If you are just
starting out, the first few specs you run should usually be harness improvements.

Primary flow: `feature spec -> run loop`.

## Command styles

- Package usage (PyPI, no clone): `uvx engineeringagent <command>`
- Package usage (version pinned): `uvx engineeringagent@<version> <command>`
- Source usage (contributors / local changes): `.engineeringagent/bin/engineeringagent <command>`

  Source usage (module entrypoint): `uv run python -m engineeringagent.cli <command>`

  Note: if you use `uv`, prefix with `uv run` so the right environment is used.

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

1. Validate and run the fast gate profile:

   ```bash
   uvx engineeringagent validate
   uvx engineeringagent gates run --profile loop_fast
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

If you are developing this repo and want to exercise local changes (not the PyPI package), run the same flow using the repo helper:

```bash
uv run .engineeringagent/bin/engineeringagent init slim
uv run .engineeringagent/bin/engineeringagent validate
uv run .engineeringagent/bin/engineeringagent gates run --profile loop_fast
```

## Bootstrapping with `init`

If you want to use the agent in one of your repositories, you can scaffold a baseline harness with:

```bash
uvx engineeringagent init
```

`init` creates a starter structure for `docs/spec/` and `harness/gates.yaml` and handles
existing `docs/` or `AGENTS.md` through explicit conflict choices.

`engineeringagent init` skips pre-commit hook installation when `.git/` does not exist.
If you want hooks installed, run `git init` before `engineeringagent init`.

`engineeringagent init` skips pre-commit hook installation when `pre-commit` is not available.

If you install `pre-commit` after running init, you can wire the hooks with `pre-commit install`.

At a minimum, `init` scaffolds:

- `docs/spec/` directories for feature specs
- `harness/gates.yaml` as a starting point for your gate profiles

It does not run gates for you or make any commits.

Warning: treat `init` as experimental scaffolding.

Always inspect generated files, run `uvx engineeringagent validate`, and review
the git diff before committing anything produced by `init`.

If you picked `standard`, your pre-commit gates are expected to fail until you disable the
demo by removing gate `demo_fail` from `harness/gates.yaml` and deleting
`harness/fitness-functions/demo_rules.yaml` and `harness/fitness-functions/demo_always_fail.py`
(or re-run: `uvx engineeringagent init slim --force`).

Use `python_uv` as a profile when you want the scaffolded `.pre-commit-config.yaml` to assume an
`uv`-based workflow and ship a minimal Python validation baseline.

In `python_uv`, the scaffolded `harness/gates.yaml` `precommit` profile includes:

- `spec_validate`
- `ruff_validate` (`uvx ruff check --isolated .`).

`python_uv` also wires a `commit-msg` hook.

```bash
uvx engineeringagent init slim --scaffold-profile python_uv
```

## What this gives you

- Deterministic progress: one spec file at a time.
- Human control: you set priorities and scope; agents execute loops.
- Built-in quality checks: validation, gates, and commit hooks.

## Run output tips

- Default output is concise; full implement/gate output stays in `progress/run-feature-<FEATURE_ID>.txt`.
- Use `--verbose-output` if you want full implement/gate output in the terminal.

## OpenCode default agent contract

- By default, `engineeringagent run` shells out to `opencode run --agent engineeringagent`
  for the implementation step.
- Your repo must have OpenCode available and configured, including an agent prompt
  like `.opencode/agents/engineeringagent.md`.
- If you are not using OpenCode, run gate profiles directly via `engineeringagent gates run --profile <profile>`.

## Human docs vs agent docs

- `README.md`: first-run, for you the developer.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper for you the developer.
- `AGENTS.md` and `docs/references/*-llms.md`: agent execution rules and deterministic procedures.

## Reviewer agents (optional)

- Reviewer agents are a harness-managed complement to deterministic gates. After initialization, config lives in `harness/reviewers.yaml`.
- `engineeringagent init` does not scaffold reviewer config or prompts. `harness/reviewers.yaml` is created by `engineeringagent reviewers init`.
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
- Agent execution map (scaffolded by init): see `AGENTS.md` (repo root)
- [Docs architecture for agents](docs/references/docs-architecture-llms.md)

## Curated external context

- [Harness engineering overview (OpenAI)](https://openai.com/index/harness-engineering/)
- [Ralph Loop background](https://ghuntley.com/loop/)
- [Agent loop patterns (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
