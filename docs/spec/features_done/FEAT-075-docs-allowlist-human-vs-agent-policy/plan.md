---
plan_id: FEAT-075
feature_id: FEAT-075
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define scaffold_policy.yaml contract and seed policy for this repo
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-002
  title: Add docs allowlist fitness script and manifest rule entry
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-003
  title: Update init to create or maintain scaffold_policy.yaml docs_root
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-004
  title: Fix allowlist policy parsing for flow-style empty lists
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_docs_allowlist_policy.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define scaffold_policy.yaml contract and seed policy for this repo

Add `harness/scaffold_policy.yaml` for engineeringagent with `docs_root=docs` and
complete allowlists for existing `docs/**/*.md` (excluding docs/spec/**).
Decide which are human vs agent docs.

## ST-002 Add docs allowlist fitness script and manifest rule entry

Add a stdlib-only harness script (under `harness/fitness-functions/`) that enforces
the allowlist policy, and declare it in `harness/fitness-functions/rules.yaml`.

## ST-003 Update init to create or maintain scaffold_policy.yaml docs_root

Ensure init writes or updates `harness/scaffold_policy.yaml` in scaffolded repos so it
matches the docs root selected by init (reuse vs separate).

## ST-004 Fix allowlist policy parsing for flow-style empty lists

The stdlib-only YAML subset parser used by the docs allowlist fitness rule must accept `human_docs: []` / `agent_docs: []` (flow-style empty lists). PyYAML emits this form for empty lists, including in init-scaffolded scaffold_policy.yaml.
