---
plan_id: FEAT-031
feature_id: FEAT-031
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Introduce prompt template artifacts and renderer module in package
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_ralph_prompt_includes_feature_file_path
- id: ST-002
  title: Migrate selector prompt generation from loop orchestration to renderer
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
- id: ST-003
  title: Migrate default implementation prompt and retry-feedback injection to renderer
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_is_injected_into_next_prompt
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_is_truncated_before_prompt_injection
- id: ST-004
  title: Add built-in hybrid prompt-locality fitness rule
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_prompt_locality.py
- id: ST-005
  title: Register and declare prompt-locality rule across fitness surfaces
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run pytest -q tests/test_validator.py
  - uv run pytest -q tests/test_fitness_catalog_generation.py
- id: ST-006
  title: Add focused loop and fitness regression coverage for prompt locality
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uv run pytest -q tests/test_fitness_rules_prompt_locality.py
- id: ST-007
  title: Run focused validation and final loop_fast gate profile
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Introduce prompt template artifacts and renderer module in package

Create in-package template files and a renderer API that can produce selector and implementation prompt text with deterministic variable substitution.

## ST-002 Migrate selector prompt generation from loop orchestration to renderer

Replace inline selector prompt assembly in loop orchestration with renderer output while preserving feature selection behavior and fallback semantics.

## ST-003 Migrate default implementation prompt and retry-feedback injection to renderer

Route default implementation prompt composition through templates/renderer, preserving retry feedback truncation/injection while making task and progress communication instructions explicit (status updates, verification, concise report).

## ST-004 Add built-in hybrid prompt-locality fitness rule

Implement `architecture.prompt-locality` in built-in fitness rules with structural and canary-content checks plus deterministic violation formatting. Include four explicit checks: template integrity, structural boundary checks, canary phrase leakage checks, and sorted deterministic result envelope output.

## ST-005 Register and declare prompt-locality rule across fitness surfaces

Wire the new built-in rule into registry metadata and explicit harness manifest declarations so list/run/catalog and gates consume it consistently.

## ST-006 Add focused loop and fitness regression coverage for prompt locality

Add pass/fail coverage for template presence, non-empty templates, locality boundary violations, canary phrase leakage, and deterministic violation ordering.

## ST-007 Run focused validation and final loop_fast gate profile

Confirm spec/fitness wiring and targeted regressions pass, then run final gate profile expected by loop execution.
