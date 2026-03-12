---
plan_id: FEAT-004
feature_id: FEAT-004
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add Ralph mode execution path for explicit feature file input
  status: done
  verification:
  - uv run engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
    --dry-run --skip-implement
- id: ST-002
  title: Implement spec-file-first OpenCode prompt contract
  status: done
  verification:
  - uv run engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
    --dry-run --skip-implement
- id: ST-003
  title: Relax subtask coupling in Ralph execution
  status: done
  verification:
  - uv run engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
    --dry-run --skip-implement
  - uv run engineeringagent validate
- id: ST-004
  title: Preserve back-pressure and telemetry in Ralph mode
  status: done
  verification:
  - uv run engineeringagent gates run --profile loop_fast
  - uv run engineeringagent run docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml
    --dry-run --skip-implement
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add Ralph mode execution path for explicit feature file input

Support running one feature-level Ralph iteration with an explicit feature spec path and no subtask orchestration requirements.

Attempts: 0

## ST-002 Implement spec-file-first OpenCode prompt contract

Build the default Ralph prompt so OpenCode is told to read the feature YAML file directly and derive its own next action.

Constraints:
- Prompt must include explicit path to active feature spec file.
- Prompt should avoid embedding subtask details from Python selection logic.

Attempts: 0

## ST-003 Relax subtask coupling in Ralph execution

Ensure Ralph mode does not block when subtasks are absent, blocked, or not selected. Feature-level state and verification outcomes should drive result semantics.

Attempts: 0

## ST-004 Preserve back-pressure and telemetry in Ralph mode

Keep gate profile execution and append one run record per non-dry iteration, including failures from implement or verification steps.

Attempts: 0
