---
plan_id: FEAT-152
feature_id: FEAT-152
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add schema registry and model-owned schema producers
  status: done
  verification:
  - uv run pytest -q tests/cli
- id: ST-002
  title: Add CLI schema command surface with list and direct id retrieval
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_checks_catalog.py
- id: ST-003
  title: Implement schema output formatting and file write support
  status: done
  verification:
  - uv run pytest -q tests/cli
- id: ST-004
  title: Remove feature schema artifact scaffold and validate sync checks
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py tests/cli/test_init_scaffold.py
- id: ST-005
  title: Update docs and scaffold references to CLI schema retrieval
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-006
  title: Run final regression and contract validation
  status: done
  verification:
  - uv run pytest -q tests/cli tests/meta/test_validator.py tests/cli/test_init_scaffold.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add schema registry and model-owned schema producers

Define stable schema ids and map them to source-model JSON Schema generation functions for feature/checks/fitness/reviewer contract surfaces.

## ST-002 Add CLI schema command surface with list and direct id retrieval

Add Typer and handler wiring for `engineeringagent schema list` and `engineeringagent schema <schema_id>`, including deterministic failure text for unknown ids and invalid usage.

## ST-003 Implement schema output formatting and file write support

Support `--format json|yaml` and optional `--output` path writing while preserving deterministic stdout semantics for automation.

## ST-004 Remove feature schema artifact scaffold and validate sync checks

Remove init scaffold generation of `docs/spec/schemas/feature.schema.json` and delete validate-time schema file synchronization checks.

## ST-005 Update docs and scaffold references to CLI schema retrieval

Update README and reference docs plus scaffolded AGENTS/contributor command guidance with one-line commands for schema listing and retrieval.

## ST-006 Run final regression and contract validation

Run targeted CLI/init/validator tests and final spec validation to confirm deterministic behavior and removal of artifact drift paths.
