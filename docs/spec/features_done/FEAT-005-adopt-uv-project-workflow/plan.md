---
plan_id: FEAT-005
feature_id: FEAT-005
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add uv lockfile and baseline project pinning
  status: done
  verification:
  - uv lock
  - uv sync
- id: ST-002
  title: Make script and gate commands uv-first
  status: done
  verification:
  - uv run python scripts/validate_specs.py
  - uv run python scripts/gates.py run --profile loop_fast
- id: ST-003
  title: Add uv docs and AGENTS.md references
  status: done
  verification:
  - uv run python scripts/validate_specs.py
  - python3 -c "from pathlib import Path; p=Path('docs/references/uv-workflow.md');
    assert p.exists(); t=Path('AGENTS.md').read_text(encoding='utf-8'); assert 'docs/references/uv-workflow.md'
    in t; print('ok')"
  - uvx --from . agent-harness --help
- id: ST-004
  title: Verify loop runner behavior under uv-managed environment
  status: done
  verification:
  - uv run agent-harness loop run --feature-id FEAT-004 --dry-run --skip-implement
  - uv run agent-harness validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add uv lockfile and baseline project pinning

Generate and commit uv.lock for deterministic dependency resolution; add project Python version pinning if needed for consistent local behavior.

Attempts: 1

## ST-002 Make script and gate commands uv-first

Update scripts and harness gate commands to execute with uv run so they use the project environment without manual activation.

Attempts: 1

## ST-003 Add uv docs and AGENTS.md references

Create or update canonical uv workflow docs under docs/ (including quickstart and common commands), refresh README references, and ensure AGENTS.md points to the uv document in its documentation map.

Attempts: 1

## ST-004 Verify loop runner behavior under uv-managed environment

Confirm loop dry-run and verification-only modes work when invoked through uv run after dependency sync.

Attempts: 1
