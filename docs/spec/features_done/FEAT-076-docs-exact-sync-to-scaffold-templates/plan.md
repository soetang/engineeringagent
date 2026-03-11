---
plan_id: FEAT-076
feature_id: FEAT-076
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add spec-writing scaffold template and wire init to scaffold it
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-002
  title: Add exact-sync fitness script and manifest entry
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-003
  title: Link scaffolded references from scaffold AGENTS and enforce with fitness
    rule
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-004
  title: Fix spec-writing doc spec validation guidance (and keep exact-sync)
  status: done
  verification:
  - uv run pytest -q tests/test_spec_writing_reference_doc.py
- id: ST-005
  title: README onboarding fixes for init-first readers
  status: done
  verification:
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py
- id: ST-006
  title: Slim init scaffold ships only valid generic fitness rules
  status: done
  verification:
  - uv run pytest -q tests/test_init_scaffold.py
- id: ST-007
  title: Post-review cleanup (tests + ruff docstrings)
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_writes_precommit_and_empty_gate_profiles
  - uv run ruff check harness/fitness_functions/check_scaffold_docs_exact_sync.py
    harness/fitness_functions/check_scaffold_template_agents_doc_links.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add spec-writing scaffold template and wire init to scaffold it

Add `src/engineeringagent/scaffold_templates/reference.spec-writing.md` and
update init to scaffold it to `${docs_root}/references/spec-writing.md`.

## ST-002 Add exact-sync fitness script and manifest entry

Implement a harness script that compares policy-declared docs to scaffold templates and
declare it in `harness/fitness_functions/rules.yaml`.

## ST-003 Link scaffolded references from scaffold AGENTS and enforce with fitness rule

Update `src/engineeringagent/scaffold_templates/AGENTS.md` to include explicit links
to each scaffolded reference doc, with 1-2 sentences describing when to consult
each file.

Add a repo fitness rule that fails when the scaffold template AGENTS does not
include all required links.

## ST-004 Fix spec-writing doc spec validation guidance (and keep exact-sync)

Remove invalid references to non-existent spec validation scripts and align the spec-writing reference doc with supported validation commands.

This doc is exact-sync between `docs/` and `src/engineeringagent/scaffold_templates/`.

## ST-005 README onboarding fixes for init-first readers

Fix or clarify the README link to `AGENTS.md` so users reading this repo before running init do not hit broken links.

Clarify first non-dry run behavior and add an explicit gates-only first-run option.

## ST-006 Slim init scaffold ships only valid generic fitness rules

Ensure the slim init scaffold does not include fitness rules that reference repository-local scripts that are not scaffolded into new repos.

## ST-007 Post-review cleanup (tests + ruff docstrings)

Fix failing regression expectations after the slim init scaffold stopped emitting repo-local fitness rules, and ensure new harness fitness scripts satisfy Ruff docstring requirements.

Notes:
- Update init regression test to expect an empty baseline fitness rules manifest.
- Add docstrings to public main() entrypoints in new harness scripts.
