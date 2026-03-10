---
plan_id: FEAT-003
feature_id: FEAT-003
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add multi-feature path input contract to run CLI
  status: done
  verification:
  - uv run engineeringagent run --help
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
    --dry-run --skip-implement
- id: ST-002
  title: Implement feature selector and repeat-until-done execution loop
  status: done
  verification:
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
    docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
- id: ST-003
  title: Add commit-gated completion and hook-feedback retry flow
  status: done
  verification:
  - uv run python scripts/gates.py run --profile precommit
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
- id: ST-004
  title: Add guardrails, telemetry, and deterministic fallback behavior
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add multi-feature path input contract to run CLI

Update run command parsing and validation to accept one or more explicit feature spec paths, with clear errors for missing or invalid files.

Attempts: 0

## ST-002 Implement feature selector and repeat-until-done execution loop

Build selector prompt that asks OpenCode to choose next pending feature from provided inputs, then run OpenCode repeatedly for that feature until status is done or a stop condition is reached.

Attempts: 0

## ST-003 Add commit-gated completion and hook-feedback retry flow

When feature status becomes done, attempt commit so hooks run. On hook failure, capture output and feed it into next OpenCode prompt for the same feature.

Attempts: 0

## ST-004 Add guardrails, telemetry, and deterministic fallback behavior

Enforce clean-tree precondition, max-iteration safety cap, deterministic selection fallback, and clear per-iteration logging in runs.jsonl and stdout summary.

Attempts: 0
