---
plan_id: FEAT-035
feature_id: FEAT-035
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add concise principles section to README with deep-dive link
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'princip' in t and 'harness' in t; print('ok')"
- id: ST-002
  title: Create human-facing deep-dive principles document
  status: done
  verification:
  - python3 -c "from pathlib import Path; p=Path('docs/principles/harness-engineering-principles.md');
    t=p.read_text(encoding='utf-8').lower(); keys=['ralph loop','progressive disclosure','yaml','automatic
    validation','fitness function','agent reviewer']; assert all(any(k in t for k
    in [key]) for key in keys); print('ok')"
- id: ST-003
  title: Apply light agent-doc alignment for discoverability
  status: done
  verification:
  - python3 -c "from pathlib import Path; paths=['AGENTS.md','docs/references/docs-architecture.md'];
    assert any('docs/principles/harness-engineering-principles.md' in Path(p).read_text(encoding='utf-8')
    for p in paths); print('ok')"
- id: ST-004
  title: Validate markdown formatting and spec integrity
  status: done
  verification:
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
    docs/principles/harness-engineering-principles.md
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add concise principles section to README with deep-dive link

Update README with a short principles summary aimed at first-run human understanding, then link to the dedicated deep-dive doc for details.

## ST-002 Create human-facing deep-dive principles document

Create `docs/principles/harness-engineering-principles.md` and cover all six concepts, clearly distinguishing current capabilities from planned items.

## ST-003 Apply light agent-doc alignment for discoverability

Add minimal references in `AGENTS.md` and/or `docs/references/docs-architecture.md` so agents can route users to the new human principles doc without blending audiences.

## ST-004 Validate markdown formatting and spec integrity

Run lightweight documentation and spec validation checks aligned with requested verification level.
