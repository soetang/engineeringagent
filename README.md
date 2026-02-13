# Engineering Agent MVP

Repo-local, human-gated harness for long-running coding loops.

## Prototype status

- This project is still prototyping; breaking changes are acceptable when they improve reliability, clarity, or loop throughput.

## Why this setup

- One feature file is the unit of loop work.
- Explicit path input keeps run behavior deterministic.
- Central gate profiles keep pre-commit wiring stable.
- Commit hooks are the final quality gate for feature completion.

## Structure

- `docs/spec/features/` active feature specs (`backlog`, `in_progress`, `blocked`).
- `docs/spec/features_done/` archived completed feature specs (`done`).
- `docs/spec/potential_features.yaml` idea backlog (not picked by loop).
- `docs/spec/schemas/feature.schema.json` schema for feature files.
- `harness/gates.yaml` gate and profile definitions.
- `progress/runs.jsonl` append-only loop telemetry.
- `harness/` domain-owned automation and gate helpers.
- `src/engineeringagent/` Python package.

## Quickstart (uv-first)

From this folder:

```bash
uv sync
uvx --from . engineeringagent init
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates list
uvx --from . engineeringagent gates run --profile loop_fast
uvx --from . engineeringagent run --all --dry-run --skip-implement
```

## Bootstrap a repository scaffold

- Run `uvx --from . engineeringagent init` to scaffold baseline harness files in one step.
- If `docs/` already exists, init requires an explicit choice to reuse it or create a separate scaffold docs directory.
- If `AGENTS.md` already exists, init offers overwrite, preserve-by-rename with scaffold regeneration, or abort.
- Re-running init is safe by default and reports skipped files unless you explicitly choose overwrite behavior.

Canonical workflow reference: `docs/references/uv-llms.md`

## Packaged CLI with uvx

Use uvx for ephemeral execution:

```bash
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates list
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
```

## Validation commands

- Precommit gates (specs + Ruff + pytest): `uvx --from . engineeringagent gates run --profile precommit`
- Ruff lint + docstrings: `uv run ruff check src/engineeringagent`
- Test: `uv run pytest -q`
- Spec validation: `uvx --from . engineeringagent validate`

## Optional editable install

```bash
uv pip install -e .
engineeringagent --help
```

## Loop behavior

- `engineeringagent run <feature-a.yaml> [feature-b.yaml ...]` keeps explicit path-first execution.
- `engineeringagent run --all` snapshots runnable active specs from `docs/spec/features/*.yaml` at startup.
- `--all` and positional feature paths are mutually exclusive.
- `--all` snapshot candidates include only `backlog` and `in_progress`; `blocked` and `done` are excluded.
- If `--all` discovers no runnable features, the command exits 0 with a no-work message.
- The runner requires no uncommitted changes before non-dry execution by default.
- Use `--allow-dirty` only when you intentionally need to run with uncommitted code changes (for example, restarting after a failed iteration with local edits still present).
- Each selected feature repeats until status is `done` and commit hooks pass.
- When a selected feature reaches `done`, the runner archives that same feature file from `docs/spec/features/` to `docs/spec/features_done/` in the same completion commit.
- If multiple feature files are pending, OpenCode selects the next feature with deterministic fallback.

## Loop CLI details

- Default implementer: `opencode run --agent build` with an auto-generated Ralph prompt.
- Default prompt contract: OpenCode is instructed to read and use the feature YAML path directly.
- Optional overrides:
  - `--implement-command "..."` to run a custom implementation command.
  - `--opencode-prompt "..."` to override the generated OpenCode prompt.
  - `--skip-implement` to execute only gates.
  - `--max-iterations` to cap non-dry retries across all selected features.
- Permission health gate: `loop_fast` includes a live OpenCode permission probe that runs `git status --short` and expects `PERMISSION_OK`.
- Logging: every non-dry iteration appends one JSONL record to `progress/runs.jsonl` with timestamp, feature id, result, failed gate, duration, attempt, and commit.

## Permission troubleshooting evidence

- Repository policy location: `.opencode/agents/build.md` plus `opencode.json`.
- Required local probe: `uvx --from . engineeringagent gates run --profile loop_fast`.
- Required gate profile: `uvx --from . engineeringagent gates run --profile loop_fast`.
- Probe failure is actionable: it fails on non-zero execution, missing `PERMISSION_OK`, or output with rejection markers such as `permission requested` or `auto-reject`.

Example non-dry loop with default OpenCode build agent:

```bash
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
```

Example auto-discovery dry-run against the startup snapshot:

```bash
uvx --from . engineeringagent run --all --dry-run --skip-implement
```

Example verification-only pass (no implement step):

```bash
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --skip-implement
```

## Pre-commit integration

`.pre-commit-config.yaml` calls a single stable entrypoint:

```bash
uvx --from . engineeringagent gates run --profile precommit
```

To change checks, edit `harness/gates.yaml` only.
