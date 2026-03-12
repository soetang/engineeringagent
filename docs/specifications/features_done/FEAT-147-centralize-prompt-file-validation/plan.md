---
plan_id: FEAT-147
feature_id: FEAT-147
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extract shared prompt_file validator in specs module
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_contract.py tests/harness/test_checks_contract.py
- id: ST-002
  title: Add regression coverage for cross-surface validation parity
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_contract.py tests/harness/test_checks_contract.py
- id: ST-003
  title: Run repository validation for spec and contract integrity
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extract shared prompt_file validator in specs module

Introduce a single helper for reviewer prompt path rules and apply it to both reviewer schema models.

## ST-002 Add regression coverage for cross-surface validation parity

Ensure both reviewer contract surfaces assert the same accepted/rejected prompt_file scenarios and guard against future drift.

## ST-003 Run repository validation for spec and contract integrity

Confirm feature spec and schema contracts remain valid after validator deduplication.
