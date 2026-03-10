---
plan_id: FEAT-002
feature_id: FEAT-002
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Implement active feature and next-subtask selection
  status: done
  verification:
  - agent-harness loop run --dry-run
- id: ST-002
  title: Implement transition guardrails and update semantics
  status: done
  verification:
  - agent-harness validate
- id: ST-003
  title: Add JSONL run logging
  status: done
  verification:
  - agent-harness loop run --dry-run
- id: ST-004
  title: Add failure policy and blocked threshold
  status: done
  verification:
  - agent-harness loop run --dry-run --max-attempts 1
- id: ST-005
  title: Add OpenCode build-agent execution configuration
  status: done
  verification:
  - python3 -c "import json; cfg=json.load(open('opencode.json')); assert cfg['model']=='openai/gpt-5.3-codex';
    assert cfg['default_agent']=='build'; assert cfg['agent']['build']['model']=='openai/gpt-5.3-codex';
    assert cfg['agent']['build']['permission']['edit']=='allow'; assert cfg['agent']['build']['permission']['webfetch']=='allow';
    assert cfg['agent']['build']['permission']['bash']['*']=='allow'; print('ok')"
  - opencode run --agent build "Reply READY"
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Implement active feature and next-subtask selection

Choose in_progress feature first; otherwise highest-priority backlog.

Attempts: 1

## ST-002 Implement transition guardrails and update semantics

Allow only declared transitions for feature and nested subtasks.

Attempts: 1

## ST-003 Add JSONL run logging

Capture ts, feature_id, subtask_id, result, failed_gate, duration, commit.

Attempts: 1

## ST-004 Add failure policy and blocked threshold

After N failed attempts, mark subtask blocked with reason.

Attempts: 1

## ST-005 Add OpenCode build-agent execution configuration

Ensure loop implementation command uses `--agent build` and repository configuration defines full build-agent permissions in `opencode.json`.

Constraints:
- Configuration should be repository-local and deterministic.
- Do not rely on interactive permission prompts during loop runs.

Attempts: 1
