---
plan_id: FEAT-081
feature_id: FEAT-081
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add canonical src fitness envelope helper
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/test_fitness_contract.py
- id: ST-002
  title: Update harness fitness functions to use src envelope helper
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-003
  title: Add harness-to-src import allowlist fitness rule
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/test_gates.py
- id: ST-004
  title: Document the supported harness helper surface
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Regenerate fitness rule catalog markdown
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_catalog_generation.py::test_repo_fitness_catalog_markdown_is_up_to_date
- id: ST-006
  title: Apply low-risk readability refactors from review
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add canonical src fitness envelope helper

Introduce `src/engineeringagent/fitness/envelope.py` that emits deterministic
JSON envelopes matching `FitnessRuleResult`, sourcing `CONTRACT_VERSION` from
`engineeringagent.fitness.contracts`.

## ST-002 Update harness fitness functions to use src envelope helper

Replace `from result_envelope import emit_result_envelope` imports in
`harness/fitness_functions/*.py` with `from engineeringagent.fitness.envelope import emit_result_envelope`.
Remove or retire the harness-local `result_envelope.py`.

## ST-003 Add harness-to-src import allowlist fitness rule

Add a new harness fitness function that scans imports in
harness fitness-rule scripts under `harness/fitness_functions/` (e.g. `check_*.py`) and fails if any `engineeringagent.*` import
is outside the allowlist (initially allow only `engineeringagent.fitness.*`).
Register the rule in `harness/fitness_functions/rules.yaml`.

## ST-004 Document the supported harness helper surface

Add a brief reference section documenting that harness scripts may depend on
`engineeringagent.fitness.*` (and only that surface by default), and that
result envelope emission must use `engineeringagent.fitness.envelope`.

## ST-005 Regenerate fitness rule catalog markdown

Ensure `docs/fitness-functions/rules.md` reflects the updated harness fitness
rules manifest and stays in sync with catalog generation.

## ST-006 Apply low-risk readability refactors from review

Tighten readability/maintenance without changing outputs.
- Simplify allowlist predicate + avoid recomputing constants. - Clean up small test formatting/duplication. - Keep diagnostics/output stable.
