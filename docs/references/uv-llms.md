# uv Workflow Reference (LLM-Oriented)

## Purpose

- Keep local development and automation on a single uv-first workflow.
- Treat `pyproject.toml` as dependency intent and `uv.lock` as resolved state.

## Quickstart

Package users (no repository checkout required):

```bash
uvx engineeringagent --help
uvx engineeringagent validate
uvx engineeringagent@<version> validate
```

Contributors (from the repository root):

```bash
uv sync
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates list
uvx --from . engineeringagent gates run --profile loop_fast
uvx --from . engineeringagent run --all --dry-run --skip-implement
```

## Daily Commands

- Validate specs: `uvx --from . engineeringagent validate`
- Scaffold baseline harness files: `uvx --from . engineeringagent init`
- List gate profiles: `uvx --from . engineeringagent gates list`
- Run loop-fast gates: `uvx --from . engineeringagent gates run --profile loop_fast`
- Run precommit gates: `uvx --from . engineeringagent gates run --profile precommit`
- Run Ruff checks (lint + docstrings): `uv run ruff check src/engineeringagent`
- Run Pyright type checks: `uv run pyright src/engineeringagent tests harness`
- Run pytest suite: `uv run pytest -q`
- Run permission probe: `uvx --from . engineeringagent gates run --profile loop_fast`
- Default OpenCode loop agent policy: `.opencode/agents/engineeringagent.md` (required; scaffolded by `engineeringagent init`). `opencode.json` is optional legacy configuration.
- CLI validate command: `uvx --from . engineeringagent validate`
- Loop dry-run command: `uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement`
- Loop auto-discovery dry-run: `uvx --from . engineeringagent run --all --dry-run --skip-implement`

## init Command Notes

- `engineeringagent init` scaffolds a baseline harness layout with deterministic defaults.
- When `docs/` exists, init requires an explicit reuse-or-separate docs decision.
- When `AGENTS.md` exists, init requires an explicit overwrite, preserve-by-rename, or abort decision.
- Default behavior is non-destructive and idempotent unless explicit overwrite/force behavior is selected.

## run --all Notes

- Use `engineeringagent run --all` to auto-discover active feature specs from `docs/spec/features/*.yaml`.
- Discovery is a one-time startup snapshot; the loop does not rescan for new specs mid-run.
- Snapshot candidates are limited to `backlog` and `in_progress` statuses.
- Features marked `blocked` or `done` are excluded from the startup snapshot.
- `--all` and positional feature paths are mutually exclusive input modes.

## Dependency Workflow

1. Edit dependencies in `pyproject.toml`.
1. Re-resolve and refresh lockfile with `uv lock`.
1. Sync the environment with `uv sync`.

## uvx Usage

- Use `uvx engineeringagent ...` for package-consumer execution from PyPI.
- Use `uvx engineeringagent@<version> ...` when you need version-pinned execution.
- Use `uvx --from . engineeringagent ...` as the canonical contributor command style.
- Keep `uv run ...` for direct tooling operations such as `pytest -q` or local Python modules.
- The `precommit` profile is the canonical quality gate and includes spec validation, Ruff lint/docstring checks, Pyright type validation, and pytest execution.
