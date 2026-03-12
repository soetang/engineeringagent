---
plan_id: FEAT-017
feature_id: FEAT-017
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define agent-focused docs architecture reference
  status: done
  verification:
  - python3 -c "from pathlib import Path; p=Path('docs/references/docs-architecture.md');
    t=p.read_text(encoding='utf-8'); lower=t.lower(); assert 'human' in lower and
    'agent' in lower and 'principle' in lower; print('ok')"
- id: ST-002
  title: Link AGENTS to docs architecture and audience policy
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('AGENTS.md').read_text(encoding='utf-8');
    lower=t.lower(); assert 'docs/references/docs-architecture.md' in t; assert 'human'
    in lower and 'agent' in lower; print('ok')"
- id: ST-003
  title: Rewrite README as purpose-driven human-first quick start
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'quickstart' in t or 'quick start' in t; assert 'spec' in t and 'run' in
    t and 'loop' in t; assert 'agent' in t and 'harness' in t; print('ok')"
- id: ST-004
  title: Add curated links for context and deeper CLI usage
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8');
    assert 'https://openai.com/index/harness-engineering/' in t; assert 'docs/references/uv-workflow.md'
    in t or 'cli' in t.lower(); print('ok')"
- id: ST-005
  title: Add mdformat check to project quality gates
  status: done
  verification:
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
  - python3 -c "from pathlib import Path; import yaml; data=yaml.safe_load(Path('harness/gates.yaml').read_text(encoding='utf-8'));
    assert 'mdformat_validate' in data.get('gates', {}); assert 'mdformat_validate'
    in data.get('profiles', {}).get('precommit', []); print('ok')"
- id: ST-006
  title: Run full validation for docs and spec integrity
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define agent-focused docs architecture reference

Create docs/references/docs-architecture.md describing doc audience boundaries, principles for human-readable docs, principles for agent-only docs, and maintenance expectations.

## ST-002 Link AGENTS to docs architecture and audience policy

Update AGENTS.md so agents discover docs/references/docs-architecture.md and follow explicit guidance on choosing human-facing versus agent-facing documentation artifacts.

## ST-003 Rewrite README as purpose-driven human-first quick start

Replace README structure with concise onboarding: what this project is, the primary `application spec -> run loop` workflow, quick start commands, core ideas, and where to go next, including explicit guidance to use agents/specs to implement harnesses.

## ST-004 Add curated links for context and deeper CLI usage

Ensure README includes the required OpenAI reference plus a small curated list of external links, and links to in-repo CLI detail documentation.

## ST-005 Add mdformat check to project quality gates

Add mdformat to development dependencies and wire an mdformat check gate into harness gate configuration so markdown formatting is validated.

## ST-006 Run full validation for docs and spec integrity

Confirm spec validation and configured gate checks pass after documentation architecture and markdown quality changes are introduced.
