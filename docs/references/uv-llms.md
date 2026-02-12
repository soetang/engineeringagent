# uv Workflow Reference (LLM-Oriented)

## Purpose

- Keep local development and automation on a single uv-first workflow.
- Treat `pyproject.toml` as dependency intent and `uv.lock` as resolved state.

## Quickstart

From the repository root:

```bash
uv sync
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates list
uvx --from . engineeringagent gates run --profile loop_fast
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
```

## Daily Commands

- Validate specs: `uvx --from . engineeringagent validate`
- Validate schema only: `uvx --from . engineeringagent validate --schema-only`
- List gate profiles: `uvx --from . engineeringagent gates list`
- Run loop-fast gates: `uvx --from . engineeringagent gates run --profile loop_fast`
- Run precommit gates: `uvx --from . engineeringagent gates run --profile precommit`
- Run Ruff checks (lint + docstrings): `uv run ruff check src/engineeringagent`
- Run pytest suite: `uv run pytest -q`
- Run permission probe: `uvx --from . engineeringagent gates run --profile loop_fast`
- Build permission policy: `.opencode/agents/build.md` and `opencode.json`
- CLI validate command: `uvx --from . engineeringagent validate`
- Loop dry-run command: `uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement`

## Dependency Workflow

1. Edit dependencies in `pyproject.toml`.
2. Re-resolve and refresh lockfile with `uv lock`.
3. Sync the environment with `uv sync`.

## uvx Usage

- Use `uvx --from . engineeringagent ...` as the canonical contributor command style.
- Keep `uv run ...` for direct tooling operations such as `pytest -q` or local Python modules.
- The `precommit` profile is the canonical quality gate and includes spec validation, Ruff lint/docstring checks, and pytest execution.
