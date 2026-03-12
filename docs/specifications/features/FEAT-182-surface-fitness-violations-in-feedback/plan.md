---
plan_id: FEAT-182
feature_id: FEAT-182
status: backlog
source_spec: spec.yaml
planning_tier: planned
phases:
  - id: P1
    title: Define the failed-fitness feedback rendering contract
    status: backlog
    verification:
      - uv run pytest -q tests/checks/test_fitness_group_port.py -k statement_budget
      - uv run pytest -q tests/checks/test_run_checks_contract.py -k prompt_feedback
  - id: P2
    title: Update shared checks feedback renderers to include remediation and violations
    status: backlog
    verification:
      - uv run pytest -q tests/checks/test_fitness_group_port.py
      - uv run pytest -q tests/loop/test_loop_phases_coverage.py -k fitness
  - id: P3
    title: Lock loop forwarding and renderer consistency with regressions
    status: backlog
    verification:
      - uv run pytest -q tests/loop/test_loop_phases_coverage.py
      - uv run pytest -q tests/checks/test_run_checks_contract.py
---

# FEAT-182 Plan

## Objective

- Render failed fitness feedback with both remediation guidance and concrete violation lines so models and humans see the exact failing files/locations on prompt-ready checks feedback surfaces.

## Approach

- Keep checks as the only owner of prompt-ready fitness feedback shaping.
- Extend the existing markdown `### Checks Failure` structure instead of introducing a new envelope format in this feature.
- Treat `violations` as first-class feedback content for any failed fitness rule that supplies them, while preserving a remediation line once per rule.
- Keep the policy general across failed fitness rules and renderers rather than adding a special case only for `architecture.module-statement-budget`.
- Preserve the current top-level failure grouping so loop/runtime and related consumers can continue forwarding checks-owned feedback without extra parsing.
- Honor the requested no-truncation policy for this feature by rendering all reported violations.

## Interfaces and Impacted Surfaces

- `src/engineeringagent/checks/strategies.py` - current fitness prompt feedback rendering drops `violations` and only emits rule id plus remediation.
- `src/engineeringagent/checks/api.py` - orchestrates the checks-owned `prompt_feedback` contract that should continue flowing unchanged to loop/runtime.
- `src/engineeringagent/loop_runtime/phases.py` - should keep forwarding checks-owned feedback verbatim, with updated regressions proving the richer failed-fitness content survives the boundary.
- `tests/checks/test_fitness_group_port.py` - currently proves rule violations appear in raw checks output and is a natural place to assert prompt-ready failed-rule rendering too.
- `tests/loop/test_loop_phases_coverage.py` - currently checks forwarded fitness feedback shape and will need updated expectations for remediation plus concrete violations.
- `tests/checks/test_run_checks_contract.py` - should lock the checks result contract around richer `prompt_feedback` content without recoupling loop logic.

## Phase Plan

### Phase 1: Define the failed-fitness feedback rendering contract

- Goal: make the intended markdown shape explicit for failed fitness rules with and without concrete violations.
- Output shape target:

```text
### Checks Failure
- check_id: `fitness_all`
- check_type: `fitness`
- failed_rules:
  - `architecture.module-statement-budget`
    - remediation: Reduce duplicated control-flow before splitting ...
    - violations:
      - `src/engineeringagent/specs.py: statements=389 cap=300`
```

- Verification:
  - `uv run pytest -q tests/checks/test_fitness_group_port.py -k statement_budget`
  - `uv run pytest -q tests/checks/test_run_checks_contract.py -k prompt_feedback`

### Phase 2: Update shared checks feedback renderers to include remediation and violations

- Goal: implement one general rendering policy for failed fitness rules across checks feedback surfaces.
- Focus: use already-captured failed-rule `violations` payload data rather than teaching loop/runtime to reconstruct failures from raw logs.
- Verification:
  - `uv run pytest -q tests/checks/test_fitness_group_port.py`
  - `uv run pytest -q tests/loop/test_loop_phases_coverage.py -k fitness`

### Phase 3: Lock loop forwarding and renderer consistency with regressions

- Goal: prove loop/runtime still forwards checks-owned feedback unchanged and that the richer failed-fitness rendering is stable across checks-facing surfaces.
- Verification:
  - `uv run pytest -q tests/loop/test_loop_phases_coverage.py`
  - `uv run pytest -q tests/checks/test_run_checks_contract.py`

## Risks and Notes

- Rendering every violation can enlarge prompt feedback significantly on noisy rules, but this feature intentionally prefers full fidelity over truncation.
- Some current regressions assert remediation-only fitness feedback and will need explicit contract updates rather than incidental string churn.
- The checks-owned boundary is important: do not let loop/runtime start formatting per-rule sections just because the feedback body is becoming richer.
