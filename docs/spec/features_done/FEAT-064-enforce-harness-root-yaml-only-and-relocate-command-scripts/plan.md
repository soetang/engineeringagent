---
plan_id: FEAT-064
feature_id: FEAT-064
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Relocate harness root scripts into harness fitness-functions and preserve
    behavior
  status: done
  verification:
  - uv run python harness/fitness-functions/validate_yaml.py
  - uv run python harness/fitness-functions/permission_probe.py
  - uv run python harness/fitness-functions/validate_commit_messages.py --help
- id: ST-002
  title: Update runtime, CI, pre-commit, and scaffold references to relocated script
    paths
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py tests/test_init_command.py
- id: ST-003
  title: Add blocking fitness rule for YAML-only harness root file locality
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_harness_root_yaml_only.py tests/test_loop_contracts.py
- id: ST-004
  title: Update docs/spec references and validate full repository contracts
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Relocate harness root scripts into harness fitness-functions and preserve behavior

Move validate_yaml, permission_probe, and validate_commit_messages scripts and update internal project-root resolution as needed.

## ST-002 Update runtime, CI, pre-commit, and scaffold references to relocated script paths

Replace all harness/*.py command references with harness/fitness-functions/*.py for active execution surfaces.

## ST-003 Add blocking fitness rule for YAML-only harness root file locality

Implement and register a command-backed rule that scans harness root and reports deterministic violations for non-YAML files.

## ST-004 Update docs/spec references and validate full repository contracts

Refresh assertions/examples that mention old harness/*.py paths and run repository-level validation/gates.
