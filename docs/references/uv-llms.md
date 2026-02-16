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
uv run python -m engineeringagent.cli validate
uv run python -m engineeringagent.cli run --all --dry-run
```

## Daily Commands

- Validate specs: `uv run python -m engineeringagent.cli validate`
- Scaffold baseline harness files: `uv run python -m engineeringagent.cli init`
- Run Ruff checks (lint + docstrings): `uv run ruff check src/engineeringagent harness`
- Run Pyright type checks: `uv run pyright src/engineeringagent tests harness`
- Run pytest suite: `uv run pytest -q`
- Default OpenCode loop agent policy: `.opencode/agents/engineeringagent.md` (required; scaffolded by `engineeringagent init`). `opencode.json` is optional legacy configuration.
- CLI validate command: `uv run python -m engineeringagent.cli validate`
- Loop dry-run command: `uv run python -m engineeringagent.cli run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run`
- Loop auto-discovery dry-run: `uv run python -m engineeringagent.cli run --all --dry-run`

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
- `engineeringagent run --dry-run` is a non-mutating preview.

## Dependency Workflow

1. Edit dependencies in `pyproject.toml`.
1. Re-resolve and refresh lockfile with `uv lock`.
1. Sync the environment with `uv sync`.

## uvx Usage

- Use `uvx engineeringagent ...` for package-consumer execution from PyPI.
- Use `uvx engineeringagent@<version> ...` when you need version-pinned execution.
- For contributor/source execution, prefer `uv run python -m engineeringagent.cli ...` to ensure you run workspace source.
- Keep `uv run ...` for direct tooling operations such as `pytest -q` or local Python modules.

### Init scaffold profile notes (slim pack)

- `core`: language-agnostic baseline scaffold (includes `harness/checks.yaml`).
- `python_uv`: Python/uv bootstrap scaffold (includes `harness/checks.yaml` plus Python-focused defaults).
- Ruff command (isolated): `uvx ruff check --isolated .`
