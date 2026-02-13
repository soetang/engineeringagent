# Python + uv + Ruff + Pyright Reference (LLM-Oriented)

## Purpose

- Keep Python contribution workflows deterministic with uv.
- Enforce linting and docstring quality with Ruff before commit.
- Enforce baseline static type validation with Pyright before commit.
- Keep precommit checks aligned with harness gate profiles.

## Canonical Workflow

From the repository root:

```bash
uv sync
uv run ruff check src/engineeringagent
uv run pyright src/engineeringagent tests harness
uv run pytest -q
uvx --from . engineeringagent gates run --profile precommit
```

## Gate and Tool Commands

- Install and sync environment: `uv sync`
- Run Ruff on package code: `uv run ruff check src/engineeringagent`
- Run targeted docstring rules: `uv run ruff check src/engineeringagent --select D103,D417`
- Run Pyright on package, tests, and harness: `uv run pyright src/engineeringagent tests harness`
- Run tests: `uv run pytest -q`
- List configured gate profiles: `uvx --from . engineeringagent gates list`
- Run loop-fast gates: `uvx --from . engineeringagent gates run --profile loop_fast`
- Run precommit gates: `uvx --from . engineeringagent gates run --profile precommit`

## Docstring Policy

- Public functions in `src/engineeringagent` must include Google-style docstrings.
- Ruff enforces missing public-function docstrings (`D103`) and argument documentation (`D417`).
- Internal helpers (names prefixed with `_`) are not treated as exported public APIs.

## Dependency and Lock Discipline

1. Update Python dependencies in `pyproject.toml`.
2. Refresh lock resolution with `uv lock`.
3. Sync local environment with `uv sync`.
4. Re-run Ruff, Pyright, and pytest checks before opening a PR.
