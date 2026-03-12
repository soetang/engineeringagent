---
plan_id: FEAT-001
feature_id: FEAT-001
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Create feature schema for nested subtasks
  status: done
  verification:
  - agent-harness validate --schema-only
- id: ST-002
  title: Implement custom validator for invariants
  status: done
  verification:
  - agent-harness validate
- id: ST-003
  title: Add pre-commit hooks for YAML and spec validation
  status: done
  verification:
  - pre-commit run --all-files
- id: ST-004
  title: Add invalid-spec fixtures and validator tests
  status: done
  verification:
  - agent-harness validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Create feature schema for nested subtasks

Define required/optional fields including free-text context fields.

Constraints:
- Schema must support nested subtasks in one feature file.

Attempts: 1

## ST-002 Implement custom validator for invariants

Add checks JSON Schema cannot express, like state transition validity, unique subtask IDs, and order constraints.

Notes:
- Enforced contiguous subtask order and done-prefix sequencing in custom validator.

Attempts: 1

## ST-003 Add pre-commit hooks for YAML and spec validation

Hook pipeline should fail fast with actionable output.

Notes:
- Added yaml_validate gate and wired it into precommit profile before spec validation.

Attempts: 1

## ST-004 Add invalid-spec fixtures and validator tests

Cover common failures: missing fields, bad status, illegal transitions.

Notes:
- Added invalid fixtures and validator tests for schema and custom transition failures.

Attempts: 1
