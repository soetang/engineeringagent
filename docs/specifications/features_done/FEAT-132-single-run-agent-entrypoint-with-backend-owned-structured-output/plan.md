---
plan_id: FEAT-132
feature_id: FEAT-132
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define single-path run-agent runtime contract and architecture alignment
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py
- id: ST-002
  title: Refactor registry and resolver to remove structured selector branching
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/agents/test_agents_helpers.py
- id: ST-003
  title: Port OpenCode backend onto single-path backend contract
  status: done
  verification:
  - uv run pytest -q tests/agents/test_opencode_backend.py tests/agents/test_opencode_client_parser.py
- id: ST-004
  title: Port Codex backend onto single-path backend contract
  status: done
  verification:
  - uv run pytest -q tests/agents/test_codex_backend.py tests/agents/test_codex_model_ids.py
    tests/agents/test_codex_scaffold.py
- id: ST-005
  title: Remove split structured interfaces and migrate in-repo call sites/tests
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/checks/test_checks_reviewers_runtime.py
- id: ST-006
  title: Audit fitness compatibility and run final verification sweep
  status: done
  verification:
  - uv run engineeringagent checks run --phase iteration_end
  - uv run engineeringagent checks run --phase feature_done --checks fitness
  - uv run engineeringagent validate
  - uv run pytest -q tests/agents/test_agents_api.py tests/agents/test_opencode_backend.py
    tests/agents/test_codex_backend.py tests/checks/test_checks_reviewers_runtime.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define single-path run-agent runtime contract and architecture alignment

Specify the normalized single-path flow and align architecture documentation wording with `output_type`-based public API behavior and backend-owned structured execution.

## ST-002 Refactor registry and resolver to remove structured selector branching

Remove `structured_output`-style backend-factory branching and ensure backend resolution occurs once per `run_agent` call.

## ST-003 Port OpenCode backend onto single-path backend contract

Keep OpenCode structured behavior backend-owned while adapting it to the unified runtime contract.

## ST-004 Port Codex backend onto single-path backend contract

Keep Codex native schema-mode behavior backend-owned while adapting it to the unified runtime contract.

## ST-005 Remove split structured interfaces and migrate in-repo call sites/tests

Delete obsolete split interfaces/runtime seams and update tests/callers to assert single-path behavior through `run_agent`.

## ST-006 Audit fitness compatibility and run final verification sweep

Confirm no fitness-rule changes are required and run full required validation commands for this contract update.
