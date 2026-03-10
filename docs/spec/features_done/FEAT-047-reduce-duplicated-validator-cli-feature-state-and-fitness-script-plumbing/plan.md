---
plan_id: FEAT-047
feature_id: FEAT-047
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Consolidate validator document-load and contract-issue append patterns
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
- id: ST-002
  title: Deduplicate feature-state failure constructors and archive mismatch message
    builders
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-003
  title: Extract shared fitness CLI metadata payload and path resolution helpers
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py
- id: ST-004
  title: Add shared fitness command-envelope helper and adopt it in harness scripts
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_adapters.py
- id: ST-005
  title: Add focused regressions for deterministic output and contract stability
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_fitness_adapters.py tests/test_loop_contracts.py
- id: ST-006
  title: Run final validation and loop-fast profile checks
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Consolidate validator document-load and contract-issue append patterns

Replace repeated YAML parse/contract-issue boilerplate with generic helpers while preserving existing message text and path formatting.

## ST-002 Deduplicate feature-state failure constructors and archive mismatch message builders

Centralize repeated `PostImplementFeatureOutcome` failure branches and archived-mismatch feedback generation in feature-state runtime helpers.

## ST-003 Extract shared fitness CLI metadata payload and path resolution helpers

Reuse deterministic helper functions for fitness JSON payload generation and manifest/output path normalization in CLI fitness commands.

## ST-004 Add shared fitness command-envelope helper and adopt it in harness scripts

Introduce one helper for command-rule JSON output envelope and use it across loop-line-budget and Ruff/dataclass script rules.

## ST-005 Add focused regressions for deterministic output and contract stability

Ensure refactors preserve output shape and deterministic ordering for CLI and command fitness adapters.

## ST-006 Run final validation and loop-fast profile checks

Validate spec contracts and repository gates after the four deduplication changes are integrated.
