---
plan_id: FEAT-089
feature_id: FEAT-089
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update repo gate/check invocations to call `uv run engineeringagent`
  status: done
  verification:
  - uv run engineeringagent --help
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-002
  title: Update local/from-source documentation to prefer `uv run engineeringagent`
  status: done
  verification:
  - uv run pytest -q tests/meta/test_docs_prefer_uv_run_engineeringagent.py
  - uv run pytest -q tests/fitness/test_fitness_rules_scaffold_docs_exact_sync.py
- id: ST-003
  title: Update fitness rule remediation strings and any policy text that references
    the old form
  status: done
  verification:
  - uv run engineeringagent fitness run --format json
  - uv run pytest -q tests/fitness/test_fitness_rules_source_first_loop_commands.py
- id: ST-004
  title: Align README and meta tests with the new local command style
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
  - uv run engineeringagent --help
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update repo gate/check invocations to call `uv run engineeringagent`

Update repo-owned check invocations and scaffold defaults to prefer `uv run engineeringagent ...` over `uv run python -m engineeringagent.cli ...` for local/from-source execution.

Primary touch points:
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yaml`
- `src/engineeringagent/scaffold_templates/precommit.python_uv.yaml`

## ST-002 Update local/from-source documentation to prefer `uv run engineeringagent`

Update repo docs that describe contributor/local verification commands.

Expected touch points include:
- `AGENTS.md` verification quick reference
- `docs/references/uv-workflow.md`
- `docs/principles/quality-check-playbook.md`
- `docs/references/docs-architecture.md` and its scaffold template
  `src/engineeringagent/scaffold_templates/reference.docs-architecture.md`
- Any other agent-only references that embed the old form.

Notes:
- Normalize Markdown list indentation in `docs/references/uv-workflow.md`.

## ST-003 Update fitness rule remediation strings and any policy text that references the old form

Update remediation strings so failures recommend the new local command style.

Expected touch points include:
- `harness/fitness_functions/check_source_first_loop_commands.py` REMEDIATION
- `harness/fitness_functions/rules.yaml` rule remediation for
  `architecture.source-first-loop-command-policy`
- `docs/fitness-functions/rules.md` (either update directly or regenerate via
  the catalog generator if that is the established workflow)

## ST-004 Align README and meta tests with the new local command style

Update README contributor/from-source guidance to use `uv run engineeringagent ...`
(while keeping `uvx engineeringagent ...` for package usage).

Update meta tests that assert the exact README command strings.
