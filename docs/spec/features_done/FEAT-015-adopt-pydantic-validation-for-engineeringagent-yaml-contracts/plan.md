---
plan_id: FEAT-015
feature_id: FEAT-015
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define strict Pydantic models and enums for feature specs
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_reports_enum_unknown_and_type_errors
  - uv run pytest -q tests/test_validator.py::test_validate_missing_required_fields_with_pydantic
- id: ST-002
  title: Migrate feature invariant rules into Pydantic validators
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_preserves_subtask_order_and_done_prefix_rules
  - uv run pytest -q tests/test_validator.py::test_validate_preserves_feature_status_invariant_rules
- id: ST-003
  title: Add Pydantic models for potential feature and gate YAML contracts
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_reports_invalid_potential_features_contract
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_rejects_invalid_contract
- id: ST-004
  title: Refactor validate command pipeline to Pydantic-only runtime path
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent validate --schema-only
- id: ST-005
  title: Generate and enforce feature JSON schema from Pydantic model
  status: done
  verification:
  - python3 -c "from pathlib import Path; import json; p=Path('docs/spec/schemas/feature.schema.json');
    data=json.loads(p.read_text(encoding='utf-8')); assert data.get('title'); print('ok')"
  - uv run pytest -q tests/test_validator.py::test_feature_schema_artifact_generated_from_pydantic_model
- id: ST-006
  title: Finalize dependency cleanup and targeted regression coverage
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py tests/test_gates.py
  - uvx --from . engineeringagent gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define strict Pydantic models and enums for feature specs

Implement typed models for feature and subtask contracts with strict enum values, forbidden extras, and field-level constraints that replace current JSON Schema shape checks.

## ST-002 Migrate feature invariant rules into Pydantic validators

Port custom invariant checks (for example subtask order contiguity, done-prefix, and feature/subtask status coupling) into Pydantic model validation so behavior is enforced in one model-driven pass.

## ST-003 Add Pydantic models for potential feature and gate YAML contracts

Extend validation coverage to `docs/spec/potential_features.yaml` and `harness/gates.yaml` with strict contract models and deterministic error reporting.

## ST-004 Refactor validate command pipeline to Pydantic-only runtime path

Update validator orchestration and CLI integration to use the new Pydantic model layer for contract validation while preserving deterministic output and exit semantics.

## ST-005 Generate and enforce feature JSON schema from Pydantic model

Add schema generation flow so `docs/spec/schemas/feature.schema.json` is derived from the Pydantic feature model and stays synchronized as a committed repository artifact.

## ST-006 Finalize dependency cleanup and targeted regression coverage

Update project dependencies/import paths for the new model-based validator and run focused regression checks for validators and CLI behavior.
