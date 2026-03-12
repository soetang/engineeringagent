---
plan_id: FEAT-008
feature_id: FEAT-008
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define allow-all build-agent permission contract
  status: done
  verification:
  - uv run python -c "import json; cfg=json.load(open('opencode.json', encoding='utf-8'));
    perm=cfg['agent']['build']['permission']; assert perm.get('*')=='allow'; print('ok')"
- id: ST-002
  title: Add permission probe command for batch bash execution
  status: done
  verification:
  - 'python3 -c "import subprocess,sys; cmd=[''opencode'',''run'',''--agent'',''build'',''Run
    exactly: git status --short. If it succeeds, reply PERMISSION_OK.'']; p=subprocess.run(cmd,capture_output=True,text=True);
    out=(p.stdout or '''')+(p.stderr or ''''); print(out); ok=(p.returncode==0 and
    ''PERMISSION_OK'' in out and ''permission requested'' not in out.lower() and ''auto-reject''
    not in out.lower()); raise SystemExit(0 if ok else 1)"'
- id: ST-003
  title: Wire permission probe into explicit validation workflow
  status: done
  verification:
  - uv run engineeringagent gates run --profile loop_fast
  - 'python3 -c "import subprocess,sys; cmd=[''opencode'',''run'',''--agent'',''build'',''Run
    exactly: git status --short. If it succeeds, reply PERMISSION_OK.'']; p=subprocess.run(cmd,capture_output=True,text=True);
    out=(p.stdout or '''')+(p.stderr or ''''); raise SystemExit(0 if p.returncode==0
    and ''PERMISSION_OK'' in out else 1)"'
- id: ST-004
  title: Add integration coverage for permission-failure signals
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define allow-all build-agent permission contract

Establish and implement one explicit allow-all policy in repository OpenCode configuration so loop runs do not rely on interactive approvals.

Notes:
- Set allow-all policy in opencode.json and added repo-local build agent override in .opencode/agents/build.md.

Attempts: 1

## ST-002 Add permission probe command for batch bash execution

Create a reproducible probe that calls OpenCode build agent and requires a successful `git status --short` execution before returning a success token.

Notes:
- Added scripts/permission_probe.py and shared probe evaluator in src/agent_harness/opencode_permissions.py.
- Live opencode probe now executes git status --short and returns PERMISSION_OK.

Attempts: 1

## ST-003 Wire permission probe into explicit validation workflow

Ensure there is a documented, repeatable validation path for permission health that can be run locally before loop execution.

Notes:
- Wired opencode_permission_probe into harness/gates.yaml loop_fast profile.
- Updated README and docs/references/uv-workflow.md with required troubleshooting evidence commands.

Attempts: 1

## ST-004 Add integration coverage for permission-failure signals

Add test coverage around permission rejection detection and loop reporting so permission failures are visible as failed gates in summaries/telemetry.

Notes:
- Added tests for permission rejection detection and failed_gate=opencode_permission telemetry reporting.

Attempts: 1
