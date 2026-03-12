---
plan_id: FEAT-168
feature_id: FEAT-168
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define generalized test-layout mirroring policy and exception contract
  status: done
  verification:
  - uv run python harness/fitness_functions/check_test_layout_module_mirroring.py
- id: ST-002
  title: Register new fitness rule and add checker regression tests
  status: done
  verification:
  - uv run pytest -q tests/fitness -k test_layout_module_mirroring
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run pytest -q tests/fitness/test_fitness_rules_catalog_docs_sync.py
- id: ST-003
  title: Move alias-root test suites to mirrored module paths
  status: done
  verification:
  - uv run pytest -q tests/git
  - uv run pytest -q tests/agents/backends/opencode
  - uv run pytest -q tests/checks/reviewers
- id: ST-004
  title: Remove legacy topic layout meta tests
  status: done
  verification:
  - uv run pytest -q tests/meta
- id: ST-005
  title: Update path literals and references affected by moved tests
  status: done
  verification:
  - uv run pytest -q tests/loop
  - uv run pytest -q tests/cli
- id: ST-006
  title: Run end-to-end policy and regression validation
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q
  - uv run engineeringagent checks run --phase iteration_end
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define generalized test-layout mirroring policy and exception contract

Implement a single checker script under `harness/fitness_functions/` plus a
policy config file that encodes explicit exception roots. The checker should
validate current repository layout (not historical move maps).

## ST-002 Register new fitness rule and add checker regression tests

Add a new `architecture.*` rule entry in `harness/fitness_functions/rules.yaml`,
add test coverage in `tests/fitness/`, and refresh generated fitness catalog docs.

## ST-003 Move alias-root test suites to mirrored module paths

Execute the cleanup move map for `vcs`, `opencode`, and `reviewers`, creating
nested module-mirroring directories where needed.

## ST-004 Remove legacy topic layout meta tests

Delete `tests/meta/test_test_layout_*_topic.py` files that encode migration-only
old->new lists, and keep layout enforcement solely in the new fitness rule.

## ST-005 Update path literals and references affected by moved tests

Update hardcoded test paths in assertions, command strings, and docs/spec references
that still point to old alias-root locations.

## ST-006 Run end-to-end policy and regression validation

Run schema validation, targeted suites, and iteration-end checks to confirm
deterministic enforcement and no policy regressions.
