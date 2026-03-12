---
plan_id: FEAT-046
feature_id: FEAT-046
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define markdown locality and reference coverage contract details
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
- id: ST-002
  title: Implement markdown locality enforcement in built-in fitness rule
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_markdown_locality.py
- id: ST-003
  title: Implement non-doc markdown reference coverage checks
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_markdown_references.py
- id: ST-004
  title: Register and declare markdown locality/reference rule across fitness surfaces
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run pytest -q tests/test_fitness_catalog_generation.py
- id: ST-005
  title: Add focused regression coverage for rule diagnostics and ordering
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_markdown_locality.py
  - uv run pytest -q tests/test_fitness_rules_markdown_references.py
- id: ST-006
  title: Run final validation and loop-fast gate checks
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define markdown locality and reference coverage contract details

Finalize approved markdown paths, explicit exceptions, ignore-directory defaults, and exact reference semantics used by enforcement.

## ST-002 Implement markdown locality enforcement in built-in fitness rule

Add deterministic markdown discovery and allowlist checks with actionable diagnostics for out-of-policy markdown locations.

## ST-003 Implement non-doc markdown reference coverage checks

Add path-based reference scanning and fail when non-doc markdown files have no non-self references.

## ST-004 Register and declare markdown locality/reference rule across fitness surfaces

Wire rule metadata into registry, add manifest declaration, and ensure list/run/catalog commands include the new rule.

## ST-005 Add focused regression coverage for rule diagnostics and ordering

Add pass/fail tests for invalid markdown locations, missing references, ignore-directory behavior, and deterministic sorted violations.

## ST-006 Run final validation and loop-fast gate checks

Validate repository contracts and run final gate profile after rule integration.
