# Engineering Agent MVP

Repo-local, human-gated harness for long-running coding loops.

## Why this setup

- One feature file is the unit of loop work.
- Explicit path input keeps run behavior deterministic.
- Central gate profiles keep pre-commit wiring stable.
- Commit hooks are the final quality gate for feature completion.

## Structure

- `docs/spec/features/` active feature specs.
- `docs/spec/features_done/` archived completed features.
- `docs/spec/potential_features.yaml` idea backlog (not picked by loop).
- `docs/spec/schemas/feature.schema.json` schema for feature files.
- `harness/gates.yaml` gate and profile definitions.
- `progress/runs.jsonl` append-only loop telemetry.
- `scripts/` thin wrappers over the CLI.
- `src/engineeringagent/` Python package.

## Quickstart (uv-first)

From this folder:

```bash
uv sync
uv run python scripts/validate_specs.py
uv run python scripts/gates.py list
uv run python scripts/permission_probe.py
bash scripts/loop.sh docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
```

Canonical workflow reference: `docs/references/uv-llms.md`

## Packaged CLI with uvx

Use uvx for ephemeral execution:

```bash
uvx --from . engineeringagent validate
uvx --from . engineeringagent gates list
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
```

## Optional editable install

```bash
uv pip install -e .
engineeringagent --help
```

## Loop behavior

- `engineeringagent run <feature-a.yaml> [feature-b.yaml ...]` is the canonical entrypoint.
- The runner requires a clean git worktree before non-dry execution.
- Each selected feature repeats until status is `done` and commit hooks pass.
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
- Required local probe: `uv run python scripts/permission_probe.py`.
- Required gate profile: `uv run python scripts/gates.py run --profile loop_fast`.
- Probe failure is actionable: it fails on non-zero execution, missing `PERMISSION_OK`, or output with rejection markers such as `permission requested` or `auto-reject`.

Example non-dry loop with default OpenCode build agent:

```bash
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
```

Example verification-only pass (no implement step):

```bash
uvx --from . engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --skip-implement
```

## Pre-commit integration

`.pre-commit-config.yaml` calls a single stable entrypoint:

```bash
uv run python scripts/gates.py run --profile precommit
```

To change checks, edit `harness/gates.yaml` only.
