---
plan_id: FEAT-180
feature_id: FEAT-180
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define repository policy and explicit allowlist shape for hermetic fitness
    tests
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-002
  title: 'Implement rule 1: repo_root-taint detection for explicit scan-target sinks'
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_hermetic_fitness_test_isolation.py
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
- id: ST-003
  title: 'Implement rule 2: forwarding-wrapper detection for explicit scan-target
    sinks'
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_hermetic_fitness_test_isolation.py
- id: ST-004
  title: Rewrite violating pytest modules and close FEAT-180 verification
  status: done
  verification:
  - uv run pytest -q tests/fitness
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define repository policy and explicit allowlist shape for hermetic fitness tests

Translate the FEAT-111 intent into a precise enforceable repository rule covering all of `tests/fitness/**`, with a small explicit integration allowlist for intentional real-repo harness coverage. Define the allowlist as policy data under `harness/fitness_functions/policies/` rather than embedded conditionals. Document that FEAT-180 is complete when the named subtasks and representative scenarios are implemented; it is not an open-ended loophole search.

## ST-002 Implement rule 1: repo_root-taint detection for explicit scan-target sinks

Implement the first finite FEAT-180 rule in a harness-local AST checker: `repo_root` and simple derived values must not reach the explicit sink list `_run_checker(..., project_root/cwd)`, `execute_rule_definition(..., project_root=...)`, or `subprocess` execution with `cwd=...`. Keep the sink list finite and spec-owned. Representative test scenarios must include one direct helper violation, one direct adapter or subprocess violation, one alias or simple derived-value violation, and one allowed script/resource lookup case.

## ST-003 Implement rule 2: forwarding-wrapper detection for explicit scan-target sinks

Implement the second finite FEAT-180 rule in the same checker: local wrappers, helper calls, or simple forwarding forms violate the rule when they pass a value into one of the explicit sink slots named by this spec. Representative test scenarios must include one local helper forwarding violation, one kwargs or forwarding violation, and one allowlisted integration case. This subtask is complete when those named scenarios pass; it does not require further exploratory syntax hunting beyond the finite rules.

## ST-004 Rewrite violating pytest modules and close FEAT-180 verification

Remove or rewrite tests that currently use `repo_root` as the scan target so they instead verify deterministic checker behavior on minimal artificial fixtures. Register the FEAT-180 rule, refresh catalog docs, and run the full verification commands. This subtask should reference the representative scenarios from ST-002 and ST-003 and close the feature once the rewritten tests and verification commands pass.
