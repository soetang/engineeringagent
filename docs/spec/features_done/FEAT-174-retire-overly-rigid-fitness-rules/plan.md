---
plan_id: FEAT-174
feature_id: FEAT-174
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove rule manifest entries and scripts for retired rules
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-002
  title: Update fitness tests impacted by rule retirement
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-003
  title: Regenerate fitness catalog documentation
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove rule manifest entries and scripts for retired rules

Remove both rule IDs from fitness manifest and delete the corresponding
checker scripts.

## ST-002 Update fitness tests impacted by rule retirement

Delete or refactor tests dedicated to removed rules so suite reflects
active rule inventory.

## ST-003 Regenerate fitness catalog documentation

Regenerate markdown catalog docs from current manifest and ensure retired
rule IDs are no longer documented.
