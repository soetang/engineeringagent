---
plan_id: FEAT-032
feature_id: FEAT-032
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Make control-flow phases explicit in run_loop and _run_feature_iteration
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-002
  title: Reduce argument fan-out using maintainable internal refactor patterns
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
- id: ST-003
  title: Extract non-control-flow iteration internals into intention-revealing helpers
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-004
  title: Enable strict PLR0913 guardrail and resolve violations with maintainable
    refactors
  status: done
  verification:
  - uv run ruff check src/engineeringagent --select PLR0913
  - uv run pytest -q tests/test_loop_ralph_mode.py
- id: ST-005
  title: Add agent guidance for PLR0913 remediation and self-documenting naming
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
- id: ST-006
  title: Run focused verification and final loop_fast gates
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Make control-flow phases explicit in run_loop and _run_feature_iteration

Keep high-level control flow easy to scan in existing orchestrators while keeping the public `engineeringagent.loop` surface stable.

## ST-002 Reduce argument fan-out using maintainable internal refactor patterns

Replace long internal helper signatures using the simplest maintainable option (phase extraction, cohesive parameter objects, keyword-only controls, typed results) while preserving behavior and readability.

## ST-003 Extract non-control-flow iteration internals into intention-revealing helpers

Move dense non-control-flow iteration logic into focused helpers/modules with clear function names while retaining compatibility seams expected by existing tests.

## ST-004 Enable strict PLR0913 guardrail and resolve violations with maintainable refactors

Turn on strict argument-budget linting and refactor internals to comply. If a compatibility-boundary exception remains, keep it narrowly scoped and documented.

## ST-005 Add agent guidance for PLR0913 remediation and self-documenting naming

Document general best-practice options for resolving wide signatures and improving variable naming clarity so future refactors converge on reusable patterns instead of ad-hoc suppressions.
Guidance draft to include in `docs/references/python-uv-ruff.md` (verbatim or equivalent):
Core intent: - Keep orchestration control flow explicit in `run_loop` and `_run_feature_iteration`. - Move non-control-flow logic (I/O details, lifecycle helpers, prompt/log formatting,
  command wrappers) into intention-revealing helpers.
- Use self-documenting variable names that communicate lifecycle/state intent.
Preferred refactor order: 1) Extract clearly named phase helpers first. 2) Reduce argument fan-out with the smallest useful pattern:
   phase extraction, cohesive parameter object/dataclass, keyword-only secondary
   controls, typed result objects.
3) Rename variables for intent, not brevity.
Example variable naming direction: - Prefer `selected_feature_path`, `archived_feature_path`, `iteration_outcome`,
  `retry_feedback_by_path`.
- Avoid overloaded generic names where lifecycle/state is knowable.
Exception policy: - No broad per-file/module `PLR0913` suppressions. - Compatibility-boundary exceptions must be narrowly scoped with inline rationale.
Verification: - `uv run ruff check src/engineeringagent --select PLR0913` - Run targeted loop tests for touched paths.
AGENTS pointer draft to include in `AGENTS.md`: - For PLR0913 remediation and self-documenting naming guidance, follow
  `docs/references/python-uv-ruff.md`.

## ST-006 Run focused verification and final loop_fast gates

Confirm refactor safety with focused loop coverage and final gate profile expected by run-loop workflows.
