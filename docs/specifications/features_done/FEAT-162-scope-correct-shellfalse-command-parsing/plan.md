---
plan_id: FEAT-162
feature_id: FEAT-162
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove embedded-pattern bans from command parser
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py::test_parse_command_argv_rejects_shell_operators
- id: ST-002
  title: Add acceptance coverage for literal shell-like arguments
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-003
  title: Update false-positive rejection tests
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Align command authoring guidance wording
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-005
  title: Keep operator-only parsing enforcement
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-006
  title: Update parser tests for no operator-token rejection
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py
- id: ST-007
  title: Update contract tests for shell-false-only enforcement
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-008
  title: Reconcile FEAT-162 narrative with new policy
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove embedded-pattern bans from command parser

Update `src/engineeringagent/process.py` to remove embedded-pattern checks for backticks and variable tokens so only explicit shell-operator token checks remain.

## ST-002 Add acceptance coverage for literal shell-like arguments

Add/update parser and contract tests that verify literal `$HOME`, `${HOME}`, and backtick strings execute as plain arguments under `shell=False`, with contract assertions that the stdout payload after the returncode line matches literal `$HOME ${HOME} \`uname\`` output exactly.

## ST-003 Update false-positive rejection tests

Remove or convert parser/contract test expectations that currently require rejection for `echo $HOME`, `echo ${HOME}`, and backtick-containing commands.

## ST-004 Align command authoring guidance wording

Update command-authoring guidance in spec-writing docs so it does not overstate that any shell-like token text is unsupported.

## ST-005 Keep operator-only parsing enforcement

Keep explicit shell-operator token blocking in `parse_command_argv` and remove broad token parsing side effects so only true operator tokens cause rejection.

## ST-006 Update parser tests for no operator-token rejection

Convert tests that currently expect parse-time failures for `|`, `&&`, redirects, and related operator tokens so behavior matches plain argv execution semantics.

## ST-007 Update contract tests for shell-false-only enforcement

Replace command-check contract assertions that depend on operator rejection and preserve only parse-error and missing-executable deterministic behavior.

## ST-008 Reconcile FEAT-162 narrative with new policy

Update objective, constraints, implementation notes, and acceptance text in this spec so they no longer require shell-operator token rejection.
