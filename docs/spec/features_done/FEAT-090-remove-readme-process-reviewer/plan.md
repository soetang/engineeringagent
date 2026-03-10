---
plan_id: FEAT-090
feature_id: FEAT-090
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove README onboarding reviewer config and delete its prompt
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Remove README onboarding reviewer scaffolding from reviewers init
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_reviewers.py
- id: ST-003
  title: Update docs to remove README onboarding reviewer references and align sandbox
    docs
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_docs_reviewer_agents_reference.py
  - uv run pytest -q tests/reviewers/test_reviewer_reference_docs.py
- id: ST-004
  title: Rename clean-room sandbox mode to empty_folder in contract validation
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_contract.py
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Implement empty_folder sandbox runtime with explicit asset copying only
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_sandbox.py
- id: ST-006
  title: Update tests to remove removed-reviewer assumptions
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Add validate-time purge invariant check (tracked files only)
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-008
  title: Remove removed-reviewer references from active specs under docs/spec/features
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove README onboarding reviewer config and delete its prompt

Remove the dedicated README onboarding/process reviewer from `harness/reviewers.yaml` (both profile inclusion and reviewer definition) and delete its prompt file under `harness/reviewers/prompts/`.

## ST-002 Remove README onboarding reviewer scaffolding from reviewers init

Update `engineeringagent reviewers init` scaffolding so it no longer generates the dedicated README onboarding reviewer entry or its prompt file.

## ST-003 Update docs to remove README onboarding reviewer references and align sandbox docs

Update reviewer reference documentation so it no longer presents the removed README onboarding reviewer as a default or copy-pastable entry. Keep examples valid without referencing removed reviewer ids. Ensure sandbox-mode documentation reflects `empty_folder`.

## ST-004 Rename clean-room sandbox mode to empty_folder in contract validation

Update the reviewer contract model so the clean-room sandbox mode enum value is `empty_folder`. Restrict `sandbox.assets` support to `empty_folder` only.

## ST-005 Implement empty_folder sandbox runtime with explicit asset copying only

Update reviewer runtime sandbox builder so `empty_folder` creates a fresh empty workspace and copies only: (1) the configured prompt file and (2) configured `sandbox.assets`. Remove any implicit asset injection. Keep existing snapshot sandbox behavior unchanged.

## ST-006 Update tests to remove removed-reviewer assumptions

Remove or refactor tests that assume the repository enables the removed README onboarding reviewer by default or that hardcode removed reviewer ids in output assertions. Replace with generic reviewer ids in test-local configs to preserve coverage of blocking retry semantics and sandbox behavior.

## ST-007 Add validate-time purge invariant check (tracked files only)

Add a validator check that uses `git ls-files` to scan tracked files for removed reviewer identifiers and removed sandbox mode names. Exclude `docs/spec/features_done/` and `progress/`. Construct the forbidden needles in code without embedding the exact forbidden tokens in the validator source to avoid self-matching.

## ST-008 Remove removed-reviewer references from active specs under docs/spec/features

Update any active specs under `docs/spec/features/` that reference removed reviewer ids or removed sandbox-mode names. Do not edit archived specs under `docs/spec/features_done/`.
