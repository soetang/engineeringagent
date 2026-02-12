# uv Workflow Reference (LLM-Oriented)

## Purpose

- Keep local development and automation on a single uv-first workflow.
- Treat `pyproject.toml` as dependency intent and `uv.lock` as resolved state.

## Quickstart

From the repository root:

```bash
uv sync
uv run python scripts/validate_specs.py
uv run python scripts/gates.py list
uv run python scripts/permission_probe.py
bash scripts/loop.sh docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
```

## Daily Commands

- Validate specs: `uv run python scripts/validate_specs.py`
- Validate schema only: `uv run python scripts/validate_specs.py --schema-only`
- List gate profiles: `uv run python scripts/gates.py list`
- Run loop-fast gates: `uv run python scripts/gates.py run --profile loop_fast`
- Run precommit gates: `uv run python scripts/gates.py run --profile precommit`
- Run permission probe: `uv run python scripts/permission_probe.py`
- Build permission policy: `.opencode/agents/build.md` and `opencode.json`
- CLI validate command: `uv run engineeringagent validate`
- Loop dry-run command: `uv run engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement`

## Dependency Workflow

1. Edit dependencies in `pyproject.toml`.
2. Re-resolve and refresh lockfile with `uv lock`.
3. Sync the environment with `uv sync`.

## uvx Usage

- Keep `uvx --from . engineeringagent ...` examples for ephemeral execution.
- Prefer `uv run ...` for repeat local development commands.
