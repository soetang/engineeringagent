# AGENTS.md

Agent operating guide for this repository.

This file is intentionally a **reference map**, not an encyclopedia.
Load only the artifacts relevant to the current task.

## 1) Mission

- Build and maintain the `agent-harness` CLI.
- Maximize reliable throughput with minimal human attention.
- Keep each loop incremental, verifiable, and recoverable.

## 2) Operating Principles

- **Humans steer, agents execute.**
- **One subtask per loop.**
- **Repository is the system of record.** If it is not in-repo, assume it does not exist.
- **Encode behavior in gates/validators.** Prefer mechanical checks over prose rules.
- **Keep this file short.** Put durable details next to code/config/docs.

## 3) System of Record (Read in this order)

1. `AGENTS.md` (this map)
2. `ARCHITECTURE.md` (high-level architecture map)
3. `docs/PLANS.md` + relevant docs under `docs/`
4. `README.md` (workflow + CLI usage)
5. `harness/gates.yaml` (active gate profiles/commands)
6. `spec/features/*.yaml` (active feature + subtasks)
7. `spec/schemas/feature.schema.json` (spec contract)
8. `src/agent_harness/` (implementation)

## 4) Repository Zones

- **Code:** `src/agent_harness/`, `scripts/`, `harness/`
- **Agent execution state:** `spec/features/`, `spec/features_done/`, `progress/runs.jsonl`
- **Backlog ideas (not loop-picked):** `spec/potential_features.yaml`
- **Architecture and docs:** `ARCHITECTURE.md`, `docs/`

## 5) Documentation Layout Reference

- `ARCHITECTURE.md`
- `docs/design-docs/index.md`
- `docs/design-docs/core-beliefs.md`
- `docs/exec-plans/active/`
- `docs/exec-plans/completed/`
- `docs/exec-plans/tech-debt-tracker.md`
- `docs/generated/db-schema.md`
- `docs/product-specs/index.md`
- `docs/product-specs/new-user-onboarding.md`
- `docs/references/design-system-reference-llms.txt`
- `docs/references/nixpacks-llms.txt`
- `docs/references/uv-llms.txt`
- `docs/DESIGN.md`
- `docs/FRONTEND.md`
- `docs/PLANS.md`
- `docs/PRODUCT_SENSE.md`
- `docs/QUALITY_SCORE.md`
- `docs/RELIABILITY.md`
- `docs/SECURITY.md`

## 6) First-Window Boot Sequence

1. Read this file, then `README.md` and `ARCHITECTURE.md`.
2. Check repo state: `git status`, recent commits.
3. Validate specs before coding.
4. Identify active feature and next eligible subtask.
5. Execute one incremental unit only.
6. Re-run gates and verification.
7. Persist outcomes for the next context window.

## 7) Loop Contract

- Advance **at most one** subtask per loop.
- Never mark subtask `done` without passing verification.
- Feature `done` requires all subtasks `done`.
- Archive completed features to `spec/features_done/`.
- Record loop outcome in `progress/runs.jsonl`.

## 8) Command Quick Reference

### Local wrappers

- Validate specs: `python3 scripts/validate_specs.py`
- Schema-only validate: `python3 scripts/validate_specs.py --schema-only`
- List gate profiles: `python3 scripts/gates.py list`
- Run precommit gates: `python3 scripts/gates.py run --profile precommit`
- Run loop-fast gates: `python3 scripts/gates.py run --profile loop_fast`
- Loop dry-run: `python3 scripts/loop.py --feature-id FEAT-001 --dry-run`
- Verify wrapper: `bash scripts/verify.sh`

### Packaged CLI (uvx)

- Help: `uvx --from . agent-harness --help`
- Validate: `uvx --from . agent-harness validate`
- Loop dry-run: `uvx --from . agent-harness loop run --feature-id FEAT-001 --dry-run`

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
