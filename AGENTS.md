# AGENTS.md

Agent operating guide for this repository.

This file is intentionally a **reference map**, not an encyclopedia.
Load only the artifacts relevant to the current task.

## 1) Mission

- Build and maintain the `engineeringagent` CLI.
- Maximize reliable throughput with minimal human attention.
- Keep each loop incremental, verifiable, and recoverable.

## 2) Operating Principles

- **Humans steer, agents execute.**
- **Audience split is explicit.** Use `README.md` for human onboarding and `AGENTS.md` plus `docs/references/*-llms.md` for agent execution guidance.
- **One feature focus per cycle.**
- **Prototype mode.** Breaking changes are acceptable when they improve reliability, clarity, or execution throughput.
- **Interview before spec-writing.** Before drafting a new feature spec, ask the user targeted questions and confirm scope.
- **Spec guide is mandatory.** Agents must follow `docs/references/spec-writing-llms.md` when authoring or updating specs.
- **Signature/naming refactors follow reference guidance.** For `PLR0913` remediation and self-documenting variable naming patterns, follow `docs/references/python-uv-ruff-llms.md`.
- **Repository is the system of record.** If it is not in-repo, assume it does not exist.
- **Encode behavior in gates/validators.** Prefer mechanical checks over prose rules.
- **Keep this file short.** Put durable details next to code/config/docs.

## 3) System of Record (Read in this order)

1. `AGENTS.md` (this map)
1. Relevant docs under `docs/` (`docs/references/spec-writing-llms.md` is required before authoring specs; `docs/references/docs-architecture-llms.md` is required before restructuring docs)
1. `README.md` (workflow + CLI usage)
1. `harness/gates.yaml` (active gate profiles/commands)
1. `docs/spec/features/` (active feature specs + subtasks, if any)
1. `docs/spec/schemas/feature.schema.json` (spec contract)
1. `src/engineeringagent/` (implementation)

## 4) Repository Zones

- **Code:** `src/engineeringagent/`, `harness/`
- **Agent execution state:** `docs/spec/features/`, `docs/spec/features_done/`, `progress/runs.jsonl`
- **Backlog ideas (not loop-picked):** `docs/spec/potential_features.yaml`
- **Documentation:** `docs/`

## 5) Documentation Layout Reference

- `docs/fitness-functions/`
- `docs/fitness-functions/README.md`
- `docs/fitness-functions/architecture.md`
- `docs/fitness-functions/rules.md`
- `docs/principles/harness-engineering-principles.md`
- `docs/references/docs-architecture-llms.md`
- `docs/references/python-uv-ruff-llms.md`
- `docs/references/spec-writing-llms.md`
- `docs/references/uv-llms.md`
- `docs/spec/features/`
- `docs/spec/features_done/*.yaml`
- `docs/spec/potential_features.yaml`
- `docs/spec/schemas/feature.schema.json`

## 6) First-Window Boot Sequence

1. Read this file, then `README.md`.
1. Check repo state: `git status`, recent commits.
1. Validate specs before coding.
1. Identify active feature and next eligible execution loop.
1. Execute one incremental unit only.
1. Re-run gates and verification.
1. Persist outcomes for the next context window.

## 7) Loop Contract

- Advance **at most one** selected feature at a time.
- Default non-dry loop execution expects no uncommitted changes.
- Non-dry runs with uncommitted code changes require explicit user opt-in via `--allow-dirty`.
- Never finalize feature `done` without passing verification and commit hooks.
- Feature completion is commit-gated in the run loop.
- On successful completion, automatically archive the selected done feature spec from `docs/spec/features/` to `docs/spec/features_done/` in the same completion commit.
- Record loop outcome in `progress/runs.jsonl`.

## 8) Command Quick Reference

### Canonical entrypoints

- Validate specs: `uvx --from . engineeringagent validate`
- Schema-only validate: `uvx --from . engineeringagent validate --schema-only`
- List gate profiles: `uvx --from . engineeringagent gates list`
- Run precommit gates: `uvx --from . engineeringagent gates run --profile precommit`
- Run loop-fast gates: `uvx --from . engineeringagent gates run --profile loop_fast`
- Loop dry-run: `uvx --from . engineeringagent run docs/spec/features/FEAT-001-spec-model-and-validator-foundation.yaml --dry-run`

### Tests (when present)

- All tests: `pytest -q`
- One file: `pytest tests/path/test_file.py -q`
- Single test: `pytest tests/path/test_file.py::test_case_name -q`
- Single method: `pytest tests/path/test_file.py::TestClass::test_method -q`

## 9) Code Standards (Reference)

- Python `>=3.10`; type hints on public APIs/CLI boundaries.
- Imports: stdlib, third-party, local; prefer absolute local imports.
- Style: PEP 8 defaults; small single-purpose functions.
- Naming: `snake_case` (funcs/modules), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- IDs: `FEAT-###`, `ST-###`, `POT-###`.
- Use `pathlib.Path`; read/write UTF-8.
- Use `subprocess.run(...)` with return-code checks and deterministic `cwd`.
- Use `ValueError` for contract violations; fail fast on invalid states.

## 10) Gate + Entropy Strategy

- Keep `.pre-commit-config.yaml` stable.
- Change checks in `harness/gates.yaml`, not hook wiring.
- Treat gate failures as control signals.
- Prefer minimal diffs; avoid unrelated refactors.
- Convert repeated feedback into validators/gates/docs.
- If a command fails, report exact command + failure point.
