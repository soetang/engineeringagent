---
plan_id: FEAT-106
feature_id: FEAT-106
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove legacy repo-root config invariant from validate (and delete its tests)
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
- id: ST-002
  title: Update pytest OpenCode integration scaffolding to use only .opencode/agents/engineeringagent.md
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_opencode_integration.py
- id: ST-003
  title: Add a repo-wide tracked-file scan verification (python -c) and run it in
    this feature
  status: done
  verification:
  - 'uv run python -c "import subprocess, sys; from pathlib import Path; proc=subprocess.run([''git'',''ls-files''],
    capture_output=True, text=True, check=True); allow_prefix=(''docs/spec/features_done/'',);
    needles=[''.''.join([''opencode'',''json'']), '' ''.join([''OpenCode'',''Json''])];
    bad=[]; root=Path(''.''); exec(''for rel in proc.stdout.splitlines():\\n    if
    not rel or rel.startswith(allow_prefix):\\n        continue\\n    p=root/rel\\n    if
    not p.is_file():\\n        continue\\n    try:\\n        text=p.read_text(encoding=\\\''utf-8\\\'',
    errors=\\\''ignore\\\'')\\n    except Exception:\\n        continue\\n    for
    n in needles:\\n        if n in text:\\n            bad.append((rel,n)); break\\n'');
    [print(f''{rel}: contains forbidden token ({n})'') for rel,n in bad]; sys.exit(1
    if bad else 0)"'
- id: ST-004
  title: Improve validator test assertion clarity for legacy config invariant removal
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove legacy repo-root config invariant from validate (and delete its tests)

## ST-002 Update pytest OpenCode integration scaffolding to use only .opencode/agents/engineeringagent.md

## ST-003 Add a repo-wide tracked-file scan verification (python -c) and run it in this feature

## ST-004 Improve validator test assertion clarity for legacy config invariant removal
