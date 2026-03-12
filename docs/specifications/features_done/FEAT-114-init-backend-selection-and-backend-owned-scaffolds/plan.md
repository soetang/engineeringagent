---
plan_id: FEAT-114
feature_id: FEAT-114
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add backend selection resolution logic to init command
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-002
  title: Persist backend choice to engineeringagent.toml during init
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-003
  title: Move OpenCode scaffold templates under agents/backends/opencode
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Refactor init_scaffold to compose baseline + backend manifest
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
  - uv run pytest -q
- id: ST-005
  title: Make init --help and model help text backend-agnostic
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-006
  title: Remove OpenCode harness toggle resolution from engineeringagent.config
  status: done
  verification:
  - uv run pytest -q tests/config
  - uv run pytest -q
- id: ST-007
  title: Clear pylint regression in config harness toggle tests
  status: done
  verification:
  - uv run pylint --score=n --reports=n src/engineeringagent tests harness
- id: ST-008
  title: Harden FEAT-114 scaffold tests around contract-level behavior
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/cli/test_init_command.py
- id: ST-009
  title: Re-run completion review for FEAT-114
  status: done
  verification:
  - uv run pytest -q
- id: ST-010
  title: Tighten backend prompt ordering and --force prompt-path assertions
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_prompts_for_backend_when_omitted_and_tty
    tests/cli/test_init_command.py::test_init_backend_prompt_invalid_input_returns_deterministic_error
    tests/cli/test_init_command.py::test_init_backend_uses_existing_config_without_prompt_unless_force
- id: ST-011
  title: Align FEAT-114 init tests with reviewer behavior-first requirements
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_explicit_non_default_backend_persists_to_engineeringagent_toml
    tests/cli/test_init_command.py::test_build_baseline_scaffold_manifest_composes_backend_manifest
- id: ST-012
  title: Archive FEAT-114 after reviewer acceptance
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-013
  title: Remove init test scaffold bypasses per reviewer feedback
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_backend_uses_existing_config_without_prompt_unless_force
    tests/cli/test_init_command.py::test_init_explicit_non_default_backend_persists_to_engineeringagent_toml
- id: ST-014
  title: Assert persisted backend selection in remaining init prompt tests
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_backend_prompt_uses_default_on_eof
    tests/cli/test_init_command.py::test_init_backend_selects_single_backend_without_prompt
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add backend selection resolution logic to init command

Add `--backend` to init. When missing and TTY, prompt using
`engineeringagent.agents.list_backends()`.

Ensure behavior matches the prompt UX contract in constraints (default/EOF/
invalid input/only-one-backend).

## ST-002 Persist backend choice to engineeringagent.toml during init

Update init to ensure engineeringagent.toml contains `[agents] backend = "..."`.

Determinism requirements:
- If the file does not exist, create it.
- If the file exists and does not contain an agents.backend value, append a
  new `[agents]` table with the selected backend.
- If the file exists and contains an agents.backend value, do not change it
  unless --force is used.

## ST-003 Move OpenCode scaffold templates under agents/backends/opencode

Relocate the OpenCode agent policy template and gitignore template out of
`src/engineeringagent/scaffold_templates/**` into backend-owned resources.

## ST-004 Refactor init_scaffold to compose baseline + backend manifest

## ST-005 Make init --help and model help text backend-agnostic

## ST-006 Remove OpenCode harness toggle resolution from engineeringagent.config

To satisfy backend-literal locality outside agents/checks, move OpenCode-named
harness toggle resolvers out of `src/engineeringagent/config.py` into
`src/engineeringagent/checks/**` (which is allowed to contain backend-specific
logic).

## ST-007 Clear pylint regression in config harness toggle tests

Resolve the retry-feedback pylint import-outside-toplevel violation in tests/config/test_config_harness_toggles.py while preserving FEAT-114 backend-literal locality behavior.

## ST-008 Harden FEAT-114 scaffold tests around contract-level behavior

Address reviewer feedback by removing brittle markdown payload assertions and internal call choreography checks in FEAT-114 scaffold tests.

## ST-009 Re-run completion review for FEAT-114

Confirm reviewer-feedback fixes satisfy completion criteria before archiving FEAT-114 under docs/spec/features_done.

## ST-010 Tighten backend prompt ordering and --force prompt-path assertions

Address follow-up reviewer feedback by asserting sorted backend-id prompt rendering/error ordering and proving --force reprompts then persists prompted/default backend selection from existing config.

## ST-011 Align FEAT-114 init tests with reviewer behavior-first requirements

Replace brittle/internal FEAT-114 init tests with behavior-first coverage for real backend manifest composition and explicit non-default --backend persistence.

## ST-012 Archive FEAT-114 after reviewer acceptance

Move FEAT-114 to docs/spec/features_done once reviewer confirms the latest test coverage updates satisfy completion criteria.

## ST-013 Remove init test scaffold bypasses per reviewer feedback

Update FEAT-114 init backend tests to exercise real scaffold writes instead of monkeypatching apply_baseline_scaffold, while keeping assertions focused on prompt behavior and persisted [agents] backend values.

## ST-014 Assert persisted backend selection in remaining init prompt tests

Address reviewer-requested gaps by asserting both EOF-default and single-backend paths persist [agents] backend in engineeringagent.toml, not just exit success.
