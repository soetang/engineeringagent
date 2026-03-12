---
plan_id: FEAT-036
feature_id: FEAT-036
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add scaffold profile contract and default core language-agnostic behavior
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_defaults_to_core_language_agnostic_profile
  - uv run pytest -q tests/test_init_command.py::test_init_python_uv_profile_available
- id: ST-002
  title: Move scaffold payloads to file-based template assets and add renderer
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_renders_scaffold_from_template_files
  - uv run pytest -q tests/test_init_command.py::test_init_template_rendering_is_deterministic
- id: ST-003
  title: Redesign scaffold AGENTS.md as minimal principles plus references map
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_generated_agents_is_reference_first_and_minimal
  - uv run pytest -q tests/test_init_command.py::test_generated_agents_keeps_major_principles
- id: ST-004
  title: Scaffold tool-generic docs pack and enforce audience boundaries
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_scaffolds_tool_generic_docs_only
  - uvx --from . engineeringagent validate
- id: ST-005
  title: Add and activate scaffold template locality fitness rule
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_scaffold_template_locality.py
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-006
  title: Dogfood AGENTS slim reference-map structure in this repository
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
  - uvx --from . engineeringagent validate
- id: ST-007
  title: Update CLI help and docs references for profile-based init
  status: done
  verification:
  - uvx --from . engineeringagent init --help
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
  - uvx --from . engineeringagent gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add scaffold profile contract and default core language-agnostic behavior

Introduce deterministic profile selection for init, defaulting to `core` and keeping stack-specific behavior explicit.

## ST-002 Move scaffold payloads to file-based template assets and add renderer

Replace inline scaffold content with template files and lightweight deterministic substitution logic for dynamic values.

## ST-003 Redesign scaffold AGENTS.md as minimal principles plus references map

Keep AGENTS short and usable: major principles plus durable references, with clear prompts for teams to fill repo-specific details incrementally.

## ST-004 Scaffold tool-generic docs pack and enforce audience boundaries

Ensure init scaffolds reusable docs for approach/workflow and does not copy repository-specific internal docs.

## ST-005 Add and activate scaffold template locality fitness rule

Implement `architecture.scaffold-template-locality` and wire it into active manifest declarations to guard against inline template regressions.

## ST-006 Dogfood AGENTS slim reference-map structure in this repository

Apply the same AGENTS information architecture locally to validate template practicality and principle alignment.

## ST-007 Update CLI help and docs references for profile-based init

Document default core profile behavior and optional profile selection in relevant human and agent docs.
