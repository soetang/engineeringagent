---
plan_id: FEAT-173
feature_id: FEAT-173
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add init launcher-selection input contract
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-002
  title: Parameterize AGENTS scaffold generation by launcher
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_scaffold.py
- id: ST-003
  title: Add tests for overwrite preserve and option-driven launcher output
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py tests/cli/test_cli_typer_parity_helpers.py
- id: ST-004
  title: Strengthen launcher wording evidence and reviewer guidance
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_agents_launcher_option_skips_prompt_even_on_tty
    tests/cli/test_init_command.py::test_init_agents_conflict_honors_explicit_launcher_option
- id: ST-005
  title: Simplify launcher resolution plumbing and test boilerplate
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py tests/cli/test_init_scaffold.py
    tests/cli/test_init_service.py
- id: ST-006
  title: Resolve reviewer feedback on launcher test evidence boundaries
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_scaffold.py::test_build_scaffold_agents_markdown_launcher_variants_are_deterministic
    tests/cli/test_init_service.py::test_run_init_command_overwrite_uses_baseline_scaffold_agents_output
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add init launcher-selection input contract

Add CLI/init request fields and resolver logic for launcher preference,
including interactive prompt and deterministic non-interactive option handling.

## ST-002 Parameterize AGENTS scaffold generation by launcher

Update AGENTS scaffold rendering to substitute selected launcher wording
without duplicating full template content across code paths.

## ST-003 Add tests for overwrite preserve and option-driven launcher output

Add or update tests for interactive selection, explicit option selection,
preserve-mode no-rewrite behavior, and overwrite-mode rewrite behavior.

## ST-004 Strengthen launcher wording evidence and reviewer guidance

Address reviewer follow-up by asserting selected launcher command tokens
in generated AGENTS output for init command flows, and refine reviewer guidance
so narrow token-level template-parameterization assertions remain allowed while
brittle full markdown-body assertions stay disallowed.

## ST-005 Simplify launcher resolution plumbing and test boilerplate

Address reviewer simplification feedback by removing dead `agents_mode`
plumbing from launcher resolver signatures/callers, making launcher choice ordering
explicit in scaffold constants, and reducing repeated launcher init arguments in
launcher-adjacent init command tests where launcher prompting is not under test.

## ST-006 Resolve reviewer feedback on launcher test evidence boundaries

Strengthen scaffold unit launcher assertions to prove token-level substitution and replace high-coupling init service choreography test with a black-box CLI overwrite scenario that validates user-observable AGENTS output.
