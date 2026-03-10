---
plan_id: FEAT-112
feature_id: FEAT-112
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add a backend-generic import boundary fitness rule
  status: done
  verification:
  - uv run python harness/fitness-functions/check_agents_backends_boundary.py
  - uv run pytest -q
- id: ST-002
  title: Register the new boundary rule in the fitness manifest
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness_all --phase iteration_end
  - uv run python harness/fitness-functions/check_agents_backends_boundary.py
- id: ST-003
  title: Add unit tests for the backend import boundary rule
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-004
  title: Add the backend literal-locality budget fitness rule
  status: done
  verification:
  - uv run python harness/fitness-functions/check_backend_literal_locality_budget.py
  - uv run pytest -q
- id: ST-005
  title: Register the literal-locality budget rule in the fitness manifest
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run python harness/fitness-functions/check_backend_literal_locality_budget.py
- id: ST-006
  title: Add unit tests for the literal-locality budget rule
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-007
  title: Make baseline refresh workflow explicit in rule output
  status: done
  verification:
  - uv run python harness/fitness-functions/check_backend_literal_locality_budget.py
- id: ST-008
  title: Address final reviewer feedback and close out feature
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py::test_backend_literal_locality_budget_rule_detects_identifier_tokens
- id: ST-009
  title: Archive completed FEAT-112 spec under features_done
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-010
  title: Add regression coverage for budget refresh metadata when observed drops below
    baseline
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py::test_backend_literal_locality_budget_rule_recommends_refresh_when_observed_drops
- id: ST-011
  title: Relax baseline-pinned literal-locality budget assertions per reviewer feedback
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add a backend-generic import boundary fitness rule

Create a new AST-based fitness script that fails when any module outside
`src/engineeringagent/agents/**` imports `engineeringagent.agents.backends`
(any backend).

## ST-002 Register the new boundary rule in the fitness manifest

## ST-003 Add unit tests for the backend import boundary rule

Add pytest coverage to verify:
- the rule is registered
- clean repo passes
- a synthetic module importing `engineeringagent.agents.backends.opencode` in
  `src/engineeringagent/*.py` causes a deterministic failure

## ST-004 Add the backend literal-locality budget fitness rule

Implement a deterministic scan for the token list described in constraints,
limited to Python files under `src/engineeringagent/**` excluding
`agents/**` and `checks/**`.

Encode a baseline count constant equal to the current repository count.

## ST-005 Register the literal-locality budget rule in the fitness manifest

## ST-006 Add unit tests for the literal-locality budget rule

Add pytest coverage to verify:
- rule registration
- baseline enforcement behavior
- violation output includes `path:line:` prefixes and is sorted
- rule output includes baseline + observed counts (in summary and/or details)

## ST-007 Make baseline refresh workflow explicit in rule output

Ensure the rule emits baseline + observed counts in a structured way so
operators can tighten the budget without re-scanning the tree manually.

## ST-008 Address final reviewer feedback and close out feature

Apply required reviewer-requested test hardening updates and rerun targeted
verification before final archival.

## ST-009 Archive completed FEAT-112 spec under features_done

Once final review is accepted, move this spec to docs/spec/features_done/ to
satisfy completion archival policy.

## ST-010 Add regression coverage for budget refresh metadata when observed drops below baseline

Add targeted pytest coverage for the zero-observed case to ensure baseline
refresh metadata remains stable when baseline is still non-zero.

## ST-011 Relax baseline-pinned literal-locality budget assertions per reviewer feedback

Replace hard-coded baseline/observed literals in backend literal-locality
tests with invariant assertions that validate metadata consistency and pass/fail
behavior as baselines change in follow-up features.
