---
plan_id: FEAT-011
feature_id: FEAT-011
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add init subcommand and baseline scaffold manifest
  status: done
  verification:
  - uvx --from . engineeringagent --help
  - uvx --from . engineeringagent init --help
  - uv run pytest -q tests/test_init_command.py::test_init_subcommand_registered
- id: ST-002
  title: Implement existing docs conflict handling flow
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_prompts_when_docs_exists
  - uv run pytest -q tests/test_init_command.py::test_init_can_use_separate_docs_directory
- id: ST-003
  title: Implement AGENTS conflict choices and follow-up merge-spec generation
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_agents_conflict_overwrite
  - uv run pytest -q tests/test_init_command.py::test_init_agents_conflict_preserve_and_create_merge_spec
  - uv run pytest -q tests/test_init_command.py::test_init_agents_conflict_abort
- id: ST-004
  title: Generate scaffold AGENTS guidance without run instructions
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_generated_agents_includes_validate_commands
  - uv run pytest -q tests/test_init_command.py::test_generated_agents_excludes_run_command_guidance
- id: ST-005
  title: Scaffold pre-commit + empty-gates baseline and friendly gate UX
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_empty_profile_returns_friendly_success_message
  - uv run pytest -q tests/test_init_command.py::test_init_writes_precommit_and_empty_gate_profiles
- id: ST-006
  title: Update docs and backlog promotion state
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('docs/spec/potential_features.yaml').read_text(encoding='utf-8');
    assert 'POT-001' not in t; print('ok')"
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add init subcommand and baseline scaffold manifest

Register `engineeringagent init` in the CLI and define the canonical baseline scaffold inventory it creates for new repositories.

## ST-002 Implement existing docs conflict handling flow

Detect existing `docs/` and require explicit choice to reuse current docs layout or create a distinct scaffold docs directory and reference it consistently.

## ST-003 Implement AGENTS conflict choices and follow-up merge-spec generation

Detect existing `AGENTS.md` and provide three-way handling: overwrite, preserve by renaming plus generate scaffold AGENTS and a follow-up merge spec, or abort without modifying files.

## ST-004 Generate scaffold AGENTS guidance without run instructions

Ensure scaffolded AGENTS content tells agents how to bootstrap/repair harness assets and run setup validation commands while intentionally excluding run-loop execution guidance.

## ST-005 Scaffold pre-commit + empty-gates baseline and friendly gate UX

Write pre-commit hook wiring and gate profile stubs with no concrete gate commands, then update CLI gate execution messaging so empty profiles produce a clear success message instead of ambiguous output.

## ST-006 Update docs and backlog promotion state

Document `engineeringagent init` usage and conflict behaviors in repo docs, and promote POT-001 by removing it from `docs/spec/potential_features.yaml`.
