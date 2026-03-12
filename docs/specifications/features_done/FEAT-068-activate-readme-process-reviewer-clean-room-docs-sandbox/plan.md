---
plan_id: FEAT-068
feature_id: FEAT-068
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Commit readme_process reviewer config + prompt and enable in loop_fast
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-002
  title: Extend reviewer schema to accept clean_room_readme_cli and sandbox.assets
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_contract.py tests/test_validator.py
- id: ST-003
  title: Include docs and configured assets in clean-room sandbox builder
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py
- id: ST-004
  title: Update reviewer authoring/reference docs for clean-room mode and assets
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Add or update regression tests for docs availability and planning semantics
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_reviewers_sandbox.py
    tests/test_loop_reviewers.py
- id: ST-006
  title: Make reviewer decision parsing resilient to wrapped JSON output
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_parse.py
- id: ST-007
  title: Fix README mdformat compliance for precommit
  status: done
  verification:
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Commit readme_process reviewer config + prompt and enable in loop_fast

Add `readme_process` to `harness/reviewers.yaml` and create
`harness/reviewers/prompts/readme_process.md` with clean-room onboarding instructions
that execute the local CLI helper (not `uvx`).

## ST-002 Extend reviewer schema to accept clean_room_readme_cli and sandbox.assets

Update reviewer contract validation (pydantic schema) to allow:
- `sandbox.mode: clean_room_readme_cli`
- optional `sandbox.assets: [<repo-relative-path>...]` for clean-room sandbox modes
  (assets may be files or directories).

## ST-003 Include docs and configured assets in clean-room sandbox builder

Extend the clean-room sandbox builder so that for `readme_process` it stages `docs/`
into the sandbox, and generally supports copying configured `sandbox.assets` entries.
Preserve guardrails against absolute paths and `..` traversal, and keep `.git`, `src/`,
and `tests/` excluded from clean-room sandboxes.

## ST-004 Update reviewer authoring/reference docs for clean-room mode and assets

Update `docs/references/reviewer-agents.md` and `docs/principles/reviewer-authoring-guide.md`
to document the `clean_room_readme_cli` sandbox mode and the `sandbox.assets` include mechanism.

## ST-005 Add or update regression tests for docs availability and planning semantics

Add focused tests that assert `docs/` exists in the clean-room sandbox for `readme_process`,
that `readme_process` plans only when `README.md` changes at `feature_done`, and that
blocking retry policy continues to behave deterministically.

## ST-006 Make reviewer decision parsing resilient to wrapped JSON output

Ensure the harness can still parse a reviewer decision when the agent runner
wraps the JSON in code fences or adds light prefix/suffix noise. This prevents
false-negative request_changes due to formatting artifacts while keeping the
required JSON decision envelope contract.
Includes a regression case where the wrapped JSON contains nested objects.

## ST-007 Fix README mdformat compliance for precommit

Format README.md to satisfy the mdformat_validate gate so README/process
changes remain reviewable and deterministic.
