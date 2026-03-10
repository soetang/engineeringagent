---
plan_id: FEAT-043
feature_id: FEAT-043
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add root parser --version flag sourced from package metadata
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_root_version_flag_outputs_installed_package_version_only
- id: ST-002
  title: Preserve root parser command requirements for non-version invocations
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_root_parser_still_requires_subcommand_without_version_flag
- id: ST-003
  title: Validate metadata contract and spec integrity
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_root_version_flag_uses_distribution_metadata_source
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add root parser --version flag sourced from package metadata

Update CLI parser wiring so `--version` prints metadata version with exact version-only output and no extra labels.

## ST-002 Preserve root parser command requirements for non-version invocations

Ensure adding `--version` does not relax existing subcommand requirements when users invoke the CLI without a command and without the version flag.

## ST-003 Validate metadata contract and spec integrity

Add coverage that the reported value comes from package metadata and run repository spec validation after updates.
