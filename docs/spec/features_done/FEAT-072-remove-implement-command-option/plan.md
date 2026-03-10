---
plan_id: FEAT-072
feature_id: FEAT-072
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove CLI option and loop wiring for implement-command
  status: done
  verification:
  - uv run python -m engineeringagent.cli run --help
  - uv run pytest -q tests/test_cli.py
- id: ST-002
  title: Remove custom implement execution path and update permission precheck text
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-003
  title: Remove docs and active-spec references
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py tests/test_spec_writing_reference_doc.py
- id: ST-004
  title: Update tests and remove implement-command assumptions
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_loop_contracts.py
  - uv run pytest -q tests/test_loop_opencode_integration.py tests/test_loop_ralph_mode.py
  - uv run python -c "from pathlib import Path; import sys; src = Path('src'); hits
    = [str(path) for path in src.rglob('*') if path.is_file() and 'implement_command'
    in path.read_text(encoding='utf-8', errors='ignore')]; print('\\n'.join(hits));
    sys.exit(1 if hits else 0)"
- id: ST-005
  title: Run full regression and ensure gates remain viable
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
- id: ST-006
  title: Align gates-only done-spec completion/archive handling
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_skip_implement_archives_done_active_feature
- id: ST-007
  title: Apply follow-up simplifications from code review
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py tests/test_loop_runtime_iteration.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove CLI option and loop wiring for implement-command

Remove the `implement-command` option from `src/engineeringagent/cli.py` and delete
all runtime plumbing that threads `implement_command` through selection/iteration
configuration and models.

## ST-002 Remove custom implement execution path and update permission precheck text

Delete the custom implement-command execution branch from
`src/engineeringagent/loop_runtime/implement.py` and adjust permission precheck
signatures and remediation hints to reference `--skip-implement` only.

## ST-003 Remove docs and active-spec references

Update `README.md` (and any other non-archived user-facing docs/help text) to remove
guidance that suggests `implement-command` as a supported execution mode.

Also remove references from other active specs under `docs/spec/features/` so the
active contract narrative matches the new CLI surface.

## ST-004 Update tests and remove implement-command assumptions

Update the test suite to remove dependencies on `implement-command` and
`implement_command` runtime wiring.

Expected touchpoints include:
- CLI option/help assertions (e.g. `tests/test_cli.py`).
- Loop contract signature assertions (e.g. `tests/test_loop_contracts.py`).
- Permission precheck messaging tests (e.g. `tests/test_loop_opencode_integration.py`).
- Ralph-mode tests that used custom implement commands as a fake implementer
  (e.g. `tests/test_loop_ralph_mode.py`), replacing that seam with OpenCode client
  stubbing (e.g. patch `engineeringagent.opencode.client.start_agent`).

Attempts: 3

## ST-005 Run full regression and ensure gates remain viable

Ensure tests and validation pass after removing the option.

Attempts: 3

## ST-006 Align gates-only done-spec completion/archive handling

When `--skip-implement` is used and a selected active spec is already `status: done`, run-loop behavior should not silently treat it as "done and committed" while leaving the file under `docs/spec/features/`.
Process that done active spec through archive + completion commit so subsequent run messaging and validation state are consistent.

Attempts: 1

## ST-007 Apply follow-up simplifications from code review

Address reviewer simplification feedback by removing dead helper code, consolidating repeated Python script execution boilerplate in Ralph-mode tests, and deduplicating the default implement-step label builder used by runtime timing and summary output.

Attempts: 1
