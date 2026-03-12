---
plan_id: FEAT-095
feature_id: FEAT-095
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add canonical $responseformat injection in reviewer runtime and enforce missing-token
    failure
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py
- id: ST-002
  title: Enforce $responseformat in reviewer markdown prompts through validator policy
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
- id: ST-003
  title: Update reviewers init and scaffold templates to generate token-based prompts
  status: done
  verification:
  - uv run pytest -q tests/test_cli_reviewers.py tests/test_init_scaffold.py
- id: ST-004
  title: Migrate repository reviewer prompts to token contract and remove bespoke
    format instructions
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_loop_reviewers.py
- id: ST-005
  title: Add human reviewer-authoring doc and link from README
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-006
  title: Update spec-writing guidance to require fitness-function impact assessment
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add canonical $responseformat injection in reviewer runtime and enforce missing-token failure

Introduce shared response-format spec text and require token-based substitution in reviewer prompt composition.

## ST-002 Enforce $responseformat in reviewer markdown prompts through validator policy

Extend validation to report deterministic contract issues when reviewer markdown prompts omit the required token.

## ST-003 Update reviewers init and scaffold templates to generate token-based prompts

Remove duplicated inline response-format prose from seeded templates and ensure generated prompts include `$responseformat`.

## ST-004 Migrate repository reviewer prompts to token contract and remove bespoke format instructions

Update existing prompt files under harness reviewer prompts to the new placeholder model.

## ST-005 Add human reviewer-authoring doc and link from README

Document human workflow for creating reviewers and response-format contract usage; wire link in README reviewer section.

## ST-006 Update spec-writing guidance to require fitness-function impact assessment

Add explicit spec-authoring instruction to evaluate whether existing fitness functions must change and record decision.
