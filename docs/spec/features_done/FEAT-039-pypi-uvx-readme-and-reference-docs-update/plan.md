---
plan_id: FEAT-039
feature_id: FEAT-039
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define uvx command matrix for package users vs contributors
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'uvx engineeringagent' in t; assert '--from .' in t; print('ok')"
- id: ST-002
  title: Update README with PyPI-first onboarding and pinning guidance
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8');
    assert 'uvx engineeringagent' in t; assert 'uvx engineeringagent@' in t; print('ok')"
- id: ST-003
  title: Align reference docs with package-consumer and contributor command styles
  status: done
  verification:
  - python3 -c "from pathlib import Path; p=Path('docs/references/uv-workflow.md');
    t=p.read_text(encoding='utf-8'); assert 'uvx engineeringagent' in t; assert '--from
    .' in t; print('ok')"
- id: ST-004
  title: Run docs formatting and spec validation checks
  status: done
  verification:
  - uv run mdformat --check README.md docs/references/uv-workflow.md
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define uvx command matrix for package users vs contributors

Establish the exact command patterns and terminology to use across docs so package-consumer (`uvx engineeringagent ...`) and contributor (`uvx --from . engineeringagent ...`) workflows are separated clearly.

## ST-002 Update README with PyPI-first onboarding and pinning guidance

Revise getting-started content in README so a first-time user can run core commands from PyPI with `uvx`, including both unpinned and version-pinned examples.

## ST-003 Align reference docs with package-consumer and contributor command styles

Update relevant files in `docs/references/` so command examples and wording consistently distinguish PyPI/uvx package usage from local contributor workflows.

## ST-004 Run docs formatting and spec validation checks

Validate formatting and spec integrity for the documentation update using the requested lightweight verification level.
