---
plan_id: FEAT-055
feature_id: FEAT-055
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add source-first loop command policy checker script
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_source_first_loop_commands.py::test_detects_forbidden_uvx_from_dot_in_feature_verification
  - uv run pytest -q tests/test_fitness_rules_source_first_loop_commands.py::test_detects_forbidden_uvx_from_dot_in_gates_config
  - uv run pytest -q tests/test_fitness_rules_source_first_loop_commands.py::test_allows_uv_run_source_first_forms
- id: ST-002
  title: Register checker as error-severity harness fitness rule
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_source_first_loop_command_rule_configuration
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
- id: ST-003
  title: Auto-migrate scoped in-repo uvx commands to source-first equivalents
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_source_first_loop_commands.py::test_repo_scoped_commands_are_policy_compliant
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-004
  title: Enforce immediate hard-fail behavior through loop fitness gate
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_fitness_gate_integration
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_includes_fitness_remediation_guidance
  - uv run python -m engineeringagent.cli gates run --profile loop_fast
- id: ST-005
  title: Update docs for command policy rationale and remediation
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
- id: ST-006
  title: Run focused regression suite for policy stability
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_source_first_loop_commands.py tests/test_gates.py
    tests/test_loop_contracts.py
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add source-first loop command policy checker script

Implement deterministic checker logic for scoped command surfaces and forbidden pattern detection.

## ST-002 Register checker as error-severity harness fitness rule

Add rule metadata and command wiring in harness fitness manifest and ensure catalog visibility.

## ST-003 Auto-migrate scoped in-repo uvx commands to source-first equivalents

Rewrite existing violations in active feature verification commands and harness gate commands while preserving behavior.

## ST-004 Enforce immediate hard-fail behavior through loop fitness gate

Ensure loop-fast gate integration blocks on policy violations and reports deterministic remediation guidance.

## ST-005 Update docs for command policy rationale and remediation

Document why in-repo loop commands must be source-first and how to remediate violations.

## ST-006 Run focused regression suite for policy stability

Verify the new fitness rule, gate enforcement, and command migrations remain deterministic.
