---
plan_id: FEAT-053
feature_id: FEAT-053
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Introduce a canonical default OpenCode agent identifier for runtime invocation
  status: done
  verification:
  - uv run pytest -q tests/test_opencode_client.py
- id: ST-002
  title: Rebase permission probe and remediation contract on engineeringagent
  status: done
  verification:
  - uv run pytest -q tests/test_opencode_permissions.py
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_exits_before_selection_when_permission_precheck_fails
- id: ST-003
  title: Update implement and selector runtime command surfaces to engineeringagent
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_selection.py
- id: ST-004
  title: Add no-fallback and non-overwrite regression coverage for existing build
    config
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_loop_reports_permission_rejection_in_run_telemetry
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_permission_precheck_failure_prints_remediation_hint
- id: ST-005
  title: Update docs for custom engineeringagent setup and permission troubleshooting
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
  - uvx --from . engineeringagent validate
- id: ST-006
  title: Run targeted OpenCode regression slice and schema validation
  status: done
  verification:
  - uv run pytest -q tests/test_opencode_client.py tests/test_opencode_permissions.py
    tests/test_loop_selection.py tests/test_loop_opencode_integration.py
  - uv run python -c "import json; cfg=json.load(open('opencode.json', encoding='utf-8'));
    agent=cfg['agent']['engineeringagent']; assert agent['model']=='openai/gpt-5.3-codex';
    assert agent.get('variant')=='high'; print('ok')"
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Introduce a canonical default OpenCode agent identifier for runtime invocation

Centralize default agent naming so OpenCode client and loop runtime call sites consistently target `engineeringagent`.

## ST-002 Rebase permission probe and remediation contract on engineeringagent

Keep executable-bash viability checks intact while enforcing no-fallback default-agent precheck and updated remediation guidance.

## ST-003 Update implement and selector runtime command surfaces to engineeringagent

Ensure runtime command execution and deterministic output strings no longer hard-code `build` for default OpenCode paths.

## ST-004 Add no-fallback and non-overwrite regression coverage for existing build config

Prove the loop still fails fast without `engineeringagent` even when `build` config exists, and does not mutate build-agent files.

## ST-005 Update docs for custom engineeringagent setup and permission troubleshooting

Align README and agent references with the new default agent and non-overwrite contract so operators can configure Codex high defaults and permissions without replacing build policy.

## ST-006 Run targeted OpenCode regression slice and schema validation

Confirm custom-agent migration is stable across unit and integration seams.
