---
plan_id: FEAT-006
feature_id: FEAT-006
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define interview-first spec authoring guide
  status: done
  verification:
  - python3 -c "from pathlib import Path; p=Path('docs/references/spec-writing.md');
    assert p.exists(); t=p.read_text(encoding='utf-8'); assert 'Hard Rule' in t and
    'Mandatory Interview Flow' in t; print('ok')"
- id: ST-002
  title: Wire AGENTS.md to the spec-writing guide
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('AGENTS.md').read_text(encoding='utf-8');
    assert 'Interview before spec-writing' in t; assert 'docs/references/spec-writing.md'
    in t; print('ok')"
- id: ST-003
  title: Define spec interview checklist for future features
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('docs/references/spec-writing.md').read_text(encoding='utf-8');
    assert 'Suggested Interview Summary Template' in t; assert 'Definition of Ready
    for Spec Drafting' in t; print('ok')"
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define interview-first spec authoring guide

Write a concise guide for LLM agents covering required interview topics, decision capture, and explicit user confirmation before drafting YAML.

Attempts: 1

## ST-002 Wire AGENTS.md to the spec-writing guide

Add explicit references in AGENTS.md so agents discover and read the guide before creating new feature specs.

Attempts: 1

## ST-003 Define spec interview checklist for future features

Include a reusable checklist/template in the guide so future spec requests consistently capture scope, constraints, and verification expectations.

Attempts: 1
