---
plan_id: FEAT-061
feature_id: FEAT-061
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove reviewer artifact generation from init scaffold internals
  status: done
  verification:
  - uv run pytest -q tests/test_init_scaffold.py
- id: ST-002
  title: Remove reviewer-specific init CLI option surfaces
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py tests/test_cli.py
- id: ST-003
  title: Update README and reviewer reference setup guidance
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove reviewer artifact generation from init scaffold internals

Delete include-reviewers scaffold branch and related template references.

## ST-002 Remove reviewer-specific init CLI option surfaces

Update parser and command wiring so init no longer accepts reviewer seeding flags.

## ST-003 Update README and reviewer reference setup guidance

Clarify that reviewer config is repository-owned and provisioned through reviewer CLI or manual harness files.
