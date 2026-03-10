---
plan_id: FEAT-122
feature_id: FEAT-122
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Migrate scaffold_policy buckets to user vs contributor
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_docs_allowlist_policy.py
  - uv run pytest -q tests/cli/test_init_command.py::test_init_scaffolds_scaffold_policy_with_resolved_docs_root
- id: ST-002
  title: Rename docs/references to drop -llms naming (and update titles)
  status: done
  verification:
  - uv run pytest -q tests/meta/test_docs_prefer_uv_run_engineeringagent.py
  - uv run pytest -q tests/meta/test_spec_writing_reference_doc.py
  - uv run pytest -q
- id: ST-003
  title: Move playbook and reviewer authoring guide into references (and update content)
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_repo_reviewers_config.py
  - uv run pytest -q tests/meta/test_docs_canonical_ruff_command.py
- id: ST-004
  title: Expand init scaffolding to include user principles and guides
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_scaffolds_tool_generic_docs_only
  - uv run pytest -q tests/fitness/test_fitness_rules_scaffold_docs_exact_sync.py
  - uv run pytest -q tests/fitness/test_fitness_rules_scaffold_template_agents_doc_links.py
- id: ST-005
  title: End-to-end validation after docs + scaffold changes
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run pytest -q
- id: ST-006
  title: Apply reviewer feedback to stabilize FEAT-122 tests
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py::test_init_scaffolds_tool_generic_docs_only
    tests/cli/test_init_command.py::test_init_scaffolds_spec_writing_reference_doc
  - uv run pytest -q tests/meta/test_docs_canonical_ruff_command.py tests/meta/test_docs_prefer_uv_run_engineeringagent.py
  - uv run pytest -q tests/fitness/test_fitness_rules_docs_allowlist_policy.py::test_docs_allowlist_checker_fails_when_doc_missing_from_both_lists
  - uv run engineeringagent validate
- id: ST-007
  title: Re-run feature-done checks and archive after reviewer acceptance
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Migrate scaffold_policy buckets to user vs contributor

Update the docs allowlist policy contract and enforcement rule:

- Replace `human_docs`/`agent_docs` with `user_docs`/`contributor_docs`.
- Update this repo's `harness/scaffold_policy.yaml` lists.
- Update init scaffolding to emit the new keys.

## ST-002 Rename docs/references to drop -llms naming (and update titles)

Rename `docs/references/*.md` to the new names and update all in-repo
references, including scaffold templates and tests. Update headings to remove
"LLM"-framed wording.

## ST-003 Move playbook and reviewer authoring guide into references (and update content)

Move operational guides out of `docs/principles/` into `docs/references/` and
update content to reflect current contracts (`harness/checks.yaml` reviewers).

## ST-004 Expand init scaffolding to include user principles and guides

Add scaffold templates for the expanded user doc set, update init to scaffold them,
and update scaffold template `AGENTS.md` links and this repo's
`harness/scaffold_policy.yaml` `scaffold_docs`/`exact_sync` to match.

## ST-005 End-to-end validation after docs + scaffold changes

Run full repository validation once all renames, policy updates, and scaffold
changes are complete.

## ST-006 Apply reviewer feedback to stabilize FEAT-122 tests

Address reviewer-requested changes by removing brittle markdown body assertions
from FEAT-122 tests and strengthening docs-allowlist violation coverage for
user_docs/contributor_docs remediation wording.

## ST-007 Re-run feature-done checks and archive after reviewer acceptance

Keep FEAT-122 active until reviewer accepts the updated test scope and the spec can be moved to docs/spec/features_done/.
