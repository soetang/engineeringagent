---
plan_id: FEAT-121
feature_id: FEAT-121
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define backend policy schema/content for literal-locality enforcement
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py
- id: ST-002
  title: Refactor backend literal-locality checker to load policy config
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py
    tests/fitness/test_fitness_adapters.py
- id: ST-003
  title: Consolidate backend boundary rule inventory on agents-backends-boundary
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_agents_backends_boundary.py
    tests/fitness/test_fitness_manifest.py tests/fitness/test_fitness_catalog_generation.py
- id: ST-004
  title: Update docs/catalog and remediation text for merged boundary policy
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run pytest -q tests/cli/test_cli_checks_catalog.py tests/fitness/test_fitness_catalog_generation.py
- id: ST-005
  title: Run full fitness/spec validation gates for merged policy change
  status: done
  verification:
  - uv run pytest -q tests/fitness
  - uv run engineeringagent validate
- id: ST-006
  title: Apply reviewer simplifications for checker metadata and manifest filtering
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py
    tests/fitness/test_fitness_rules_agents_backends_boundary.py
  - uv run engineeringagent validate
- id: ST-007
  title: Address reviewer warning follow-ups for readability consistency
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_backend_literal_locality_budget.py
  - uv run engineeringagent validate
- id: ST-008
  title: Archive completed feature spec to features_done
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define backend policy schema/content for literal-locality enforcement

Add policy configuration under `harness/fitness-functions/policies/` for backend token sets keyed by backend id; seed with opencode and codex entries.

## ST-002 Refactor backend literal-locality checker to load policy config

Replace hardcoded OpenCode token tuple with policy-backed token loading and deterministic validation/error handling.

## ST-003 Consolidate backend boundary rule inventory on agents-backends-boundary

Remove `architecture.agents-opencode-boundary` from manifest and retire/replace overlapping script/tests while preserving required boundary coverage under `architecture.agents-backends-boundary`.

## ST-004 Update docs/catalog and remediation text for merged boundary policy

Regenerate fitness catalog docs and align remediation/rationale wording with consolidated boundary contract and policy-driven literal checks.

## ST-005 Run full fitness/spec validation gates for merged policy change

Run targeted and full validation to ensure rule-inventory changes are stable and no stale rule-id references remain.

## ST-006 Apply reviewer simplifications for checker metadata and manifest filtering

Address reviewer warning by extracting duplicated backend-literal error baseline metadata assignment into a helper and replacing manifest rule-id filtering loops with direct comprehensions.

## ST-007 Address reviewer warning follow-ups for readability consistency

Apply code-simplifier feedback by using a comprehension for backend-literal manifest filtering and deduplicating repeated list-validation error message text in backend literal policy parsing.

## ST-008 Archive completed feature spec to features_done

Move FEAT-121 spec into docs/spec/features_done once final validation and reviewer follow-ups are fully accepted.
