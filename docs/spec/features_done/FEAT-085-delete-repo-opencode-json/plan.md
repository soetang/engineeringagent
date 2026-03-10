---
plan_id: FEAT-085
feature_id: FEAT-085
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove repo-root opencode.json and confirm no runtime dependency
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Update docs to avoid requiring opencode.json
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/reviewers/test_repo_reviewers_config.py
- id: ST-003
  title: Lock in invariants with lightweight search assertions
  status: done
  verification:
  - uv run pytest -q
  - uv run python -c "from pathlib import Path; roots=[Path('src'),Path('docs'),Path('README.md')];
    hits=[]\nfor root in roots:\n    paths=[root] if root.is_file() else [p for p
    in root.rglob('*') if p.is_file()]\n    for p in paths:\n        posix=p.as_posix()\n        if
    '/docs/spec/' in posix or posix.startswith('docs/spec/'):\n            continue\n        text=p.read_text(encoding='utf-8',
    errors='ignore')\n        if 'opencode.json' in text:\n            hits.append(str(p))\nprint('\\n'.join(hits));\nraise
    SystemExit(1 if hits else 0)"
- id: ST-004
  title: Run regression gates
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run engineeringagent checks run --phase iteration_end
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove repo-root opencode.json and confirm no runtime dependency

Delete `opencode.json` from the repository root and confirm nothing in
`src/engineeringagent/` requires it.

## ST-002 Update docs to avoid requiring opencode.json

Ensure active docs (README and docs/references) emphasize the shipped policy
file `.opencode/agents/engineeringagent.md` and do not imply `opencode.json`
is required.

## ST-003 Lock in invariants with lightweight search assertions

Add or update tests/validation checks to ensure we do not regress and
accidentally re-introduce a dependency on repo-root `opencode.json`.

## ST-004 Run regression gates

Run the standard validation and gate profile used for loop iterations.
