---
plan_id: FEAT-102
feature_id: FEAT-102
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update hello-world feature template verification to uv
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-002
  title: Run uv init in the smoke temp repo and switch post-run verification to uv
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-003
  title: Add/adjust tests to enforce uv-based verification behavior
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update hello-world feature template verification to uv

Update harness/fitness_functions/real_opencode_hello_world_feature_template.yaml so all verification commands use `uv run python` and the template text reflects that uv init creates a minimal pyproject.toml which must not be modified.

## ST-002 Run uv init in the smoke temp repo and switch post-run verification to uv

Update harness/fitness_functions/check_real_opencode_hello_world_smoke.py to run `uv init . --package --vcs none --no-readme --no-pin-python` in the temp repo root and to run all post-run verification commands via `uv run python`.

## ST-003 Add/adjust tests to enforce uv-based verification behavior

Add or update tests to ensure the feature template verification commands use `uv run python` and that the harness verification helper no longer invokes PATH python directly.
