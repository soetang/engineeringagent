---
plan_id: FEAT-054
feature_id: FEAT-054
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add scaffolded code_simplifier reviewer entry and upstream-copied prompt
    file
  status: done
  verification:
  - uv run pytest -q tests/test_init_scaffold.py
- id: ST-002
  title: Add planner matching for code-scoped on-change selectors at iteration_end
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_code_simplifier_plans_only_for_code_scoped_changes
- id: ST-003
  title: Enforce advisory follow-up pass behavior for code_simplifier outcomes
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_code_simplifier_advisory_requires_one_followup_implement_pass
- id: ST-004
  title: Keep advisory non-blocking semantics with deterministic telemetry
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_code_simplifier_advisory_does_not_hard_block_by_default
  - uv run pytest -q tests/test_loop_output.py
- id: ST-005
  title: Add docs section with exact code_simplifier sample and policy explanation
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
- id: ST-006
  title: Update markdown locality policy for reviewer prompt markdown path
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_markdown_locality.py tests/test_fitness_rules_markdown_references.py
- id: ST-007
  title: Run reviewer-specific regression slice
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_loop_reviewers.py
    tests/test_loop_contracts.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add scaffolded code_simplifier reviewer entry and upstream-copied prompt file

Add default code_simplifier reviewer example and prompt artifact to scaffold output, seeded from `/home/soetang/.config/opencode/agent/code-simplifier.md`.

## ST-002 Add planner matching for code-scoped on-change selectors at iteration_end

Ensure planner schedules code_simplifier only when code paths changed and phase matches.

## ST-003 Enforce advisory follow-up pass behavior for code_simplifier outcomes

Ensure advisory decisions from code_simplifier trigger required implement follow-up latch.

## ST-004 Keep advisory non-blocking semantics with deterministic telemetry

Ensure code_simplifier does not force hard-fail by default and emits stable telemetry/summaries.

## ST-005 Add docs section with exact code_simplifier sample and policy explanation

Document code_simplifier trigger, advisory semantics, and follow-up behavior in plain English.

## ST-006 Update markdown locality policy for reviewer prompt markdown path

Keep reviewer prompts under harness path compliant with markdown locality and reference coverage checks.

## ST-007 Run reviewer-specific regression slice

Validate planner and loop behavior for code_simplifier scenario end to end.
