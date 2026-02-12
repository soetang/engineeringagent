# Agent Harness MVP

Repo-local, human-gated harness for long-running coding loops.

## Why this setup

- One feature file is the unit of loop work
- Archive completed features to keep active context small
- Central gate profiles so pre-commit config stays stable
- One loop run processes one feature iteration at most

## Structure

- `docs/spec/features/` active feature specs
- `docs/spec/features_done/` archived completed features
- `docs/spec/potential_features.yaml` idea backlog (not picked by loop)
- `docs/spec/schemas/feature.schema.json` schema for feature files
- `harness/gates.yaml` gate and profile definitions
- `progress/runs.jsonl` append-only loop telemetry
- `scripts/` thin wrappers over the CLI
- `src/agent_harness/` Python package

## Quickstart (uv-first)

From this folder:

```bash
uv sync
uv run python scripts/validate_specs.py
uv run python scripts/gates.py list
uv run python scripts/permission_probe.py
bash scripts/loop.sh --feature-id FEAT-002 --dry-run --skip-implement
```

Canonical workflow reference: `docs/references/uv-llms.md`

## Packaged CLI with uvx

Use uvx for ephemeral execution:

```bash
uvx --from . agent-harness validate
uvx --from . agent-harness gates list
uvx --from . agent-harness loop run --feature-id FEAT-002 --dry-run --skip-implement
```

## Optional editable install

```bash
uv pip install -e .
agent-harness --help
```

## Loop behavior

- `agent-harness loop run` runs one feature iteration max.
- If a selected feature is marked `done`, it is archived to `docs/spec/features_done/`.
- If `--feature-id` is provided, selection is pinned to that feature.

## Loop CLI details

- Feature selection: pick `in_progress` first, otherwise highest-priority `backlog`.
- Default implementer: runs `opencode run --agent build` with an auto-generated prompt.
- Default prompt contract: OpenCode is instructed to read and use the feature YAML file path directly.
- Optional overrides:
  - `--implement-command "..."` to run a custom implementation command.
  - `--opencode-prompt "..."` to override the generated OpenCode prompt.
  - `--skip-implement` to execute only gates.
- Permission health gate: `loop_fast` includes a live OpenCode permission probe that runs `git status --short` and expects `PERMISSION_OK`.
- Transition guardrails: loop enforces legal feature status transitions.
- Logging: every non-dry-run loop appends one JSONL record to `progress/runs.jsonl` with timestamp, feature id, result, failed gate, duration, and commit.

## Permission troubleshooting evidence

- Repository policy location: `.opencode/agents/build.md` (agent override) plus `opencode.json` (project config)
- Required local probe: `uv run python scripts/permission_probe.py`
- Required gate profile: `uv run python scripts/gates.py run --profile loop_fast`
- Probe failure is actionable: it fails on non-zero execution, missing `PERMISSION_OK`, or output that includes rejection markers such as `permission requested` or `auto-reject`.

Example non-dry loop with default OpenCode build agent:

```bash
uvx --from . agent-harness loop run --feature-id FEAT-002
```

Example verification-only pass (no implement step):

```bash
uvx --from . agent-harness loop run --feature-id FEAT-002 --skip-implement
```

## Pre-commit integration

`.pre-commit-config.yaml` calls a single stable entrypoint:

```bash
uv run python scripts/gates.py run --profile precommit
```

To change checks, edit `harness/gates.yaml` only.
