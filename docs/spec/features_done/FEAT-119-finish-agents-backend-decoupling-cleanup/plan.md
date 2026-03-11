---
plan_id: FEAT-119
feature_id: FEAT-119
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove backend override from run_agent public contract
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py
- id: ST-002
  title: Remove reviewer backend override seam
  status: done
  verification:
  - uv run pytest -q tests/reviewers
- id: ST-003
  title: Migrate tests to registry+config backend injection
  status: done
  verification:
  - uv run pytest -q tests/agents
- id: ST-004
  title: Remove agents_defaults by internalizing OpenCode default agent id
  status: done
  verification:
  - uv run python harness/fitness_functions/check_backend_literal_locality_budget.py
  - uv run pytest -q
- id: ST-005
  title: Restore backend-owned scaffold template markdown and adjust fitness rules
  status: done
  verification:
  - uv run python harness/fitness_functions/check_markdown_locality_reference_coverage.py
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_locality.py tests/fitness/test_fitness_rules_markdown_references.py
- id: ST-006
  title: Tighten backend literal-locality budget baseline to zero
  status: done
  verification:
  - uv run python harness/fitness_functions/check_backend_literal_locality_budget.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
- id: ST-007
  title: Update FEAT-117 spec to match no-backend-override contract
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove backend override from run_agent public contract

Update `engineeringagent.agents.run_agent` to remove the `backend` parameter and
rely exclusively on internal backend resolution.

## ST-002 Remove reviewer backend override seam

Remove `ReviewerRunRequest.agent_backend` and stop passing any backend object into
`run_agent` from reviewer execution.

## ST-003 Migrate tests to registry+config backend injection

Replace direct `backend=` injection with:
- a temp `engineeringagent.toml` containing `[agents] backend = "<id>"`
- registry mapping injection via monkeypatching/registering backend factories.

## ST-004 Remove agents_defaults by internalizing OpenCode default agent id

Move the OpenCode default agent id constant under the OpenCode backend package and
delete `src/engineeringagent/agents_defaults.py`.

## ST-005 Restore backend-owned scaffold template markdown and adjust fitness rules

Rename `agent.engineeringagent.template` back to a `.md` asset and update the
markdown locality/reference-coverage fitness rule to allow backend-owned scaffold
markdown without requiring non-self references.

## ST-006 Tighten backend literal-locality budget baseline to zero

Update the budget baseline constant to 0 and ensure the repository remains clean.

## ST-007 Update FEAT-117 spec to match no-backend-override contract

Update FEAT-117 constraints/acceptance/notes to remove any mention of
`run_agent(..., backend=...)` and to state that backend selection is internal to
`engineeringagent.agents`.
