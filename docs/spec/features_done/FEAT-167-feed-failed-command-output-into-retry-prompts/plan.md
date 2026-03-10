---
plan_id: FEAT-167
feature_id: FEAT-167
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Enrich checks command-failure prompt feedback with output excerpts
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py -k prompt_feedback
- id: ST-002
  title: Enrich verification command-failure feedback with output excerpts
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py -k verification
  - uv run pytest -q tests/loop/test_feedback_contracts.py -k command_failure
- id: ST-003
  title: Add focused regression tests for latest-only retry context
  status: done
  verification:
  - uv run pytest -q tests/loop/test_feedback_contracts.py
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py
- id: ST-004
  title: Run schema validation and targeted iteration-end checks
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run engineeringagent checks run --phase iteration_end
- id: ST-006
  title: Centralize feedback envelope parsing test helper
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-007
  title: Simplify reviewer backend recoverability check for readability
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Enrich checks command-failure prompt feedback with output excerpts

Extend checks command-failure feedback to include recent failed-command output
excerpts that are actionable for retries.

## ST-002 Enrich verification command-failure feedback with output excerpts

Include failed-command output excerpts in verification retry feedback for the
next implement pass.

## ST-003 Add focused regression tests for latest-only retry context

Verify repeated failures replace prior retry context and forward only the latest
failure excerpt.

## ST-004 Run schema validation and targeted iteration-end checks

Confirm contracts and loop/checks boundaries remain valid after feedback enrichment.

## ST-006 Centralize feedback envelope parsing test helper

Replace duplicate prompt-envelope parsers in loop tests with a shared utility
and move retry-context assertions to envelope contracts.

## ST-007 Simplify reviewer backend recoverability check for readability

Refactor the review command decision fallback condition into a named helper to satisfy code simplifier feedback and keep the retry recovery branch linear.
