---
plan_id: FEAT-165
feature_id: FEAT-165
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Switch canonical progress path helpers to hidden namespace
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_feature_iteration.py -k progress
  - uv run pytest -q tests/loop/test_loop_opencode_integration.py -k progress
- id: ST-002
  title: Migrate loop and CLI progress writers to new canonical path
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py -k progress
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py
- id: ST-003
  title: Update validation exclusions and path-sensitive repo policies
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
- id: ST-004
  title: Retarget progress locality fitness rule to hidden path
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_catalog_docs_sync.py
  - uv run python harness/fitness_functions/check_progress_log_locality.py
- id: ST-005
  title: Add init scaffold and docs guidance for ignoring runtime artifacts
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_scaffold.py
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-006
  title: Update user-facing and scaffolded workflow path examples
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_references.py
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_locality.py
- id: ST-007
  title: Run full repository verification for path migration
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks run --phase iteration_end
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Switch canonical progress path helpers to hidden namespace

Update progress path constructors to resolve `.engineeringagent/progress/...` and
preserve deterministic repo-relative references consumed by telemetry/presentation.

## ST-002 Migrate loop and CLI progress writers to new canonical path

Ensure implement/telemetry/handoff/prune flows and reviewer state persistence all
write/read through updated path helpers with no lingering `progress/` assumptions.

## ST-003 Update validation exclusions and path-sensitive repo policies

Align validator exclusions (for tracked-file scans and similar path-sensitive policy
logic) with `.engineeringagent/progress/` so policy behavior remains intentional.

## ST-004 Retarget progress locality fitness rule to hidden path

Update progress locality rule literals/docs to enforce `.engineeringagent/progress/...`
while preserving existing constraints on centralized path construction and write sinks.

## ST-005 Add init scaffold and docs guidance for ignoring runtime artifacts

Implement deterministic scaffold behavior and documentation language that clearly marks
`.engineeringagent/progress/` as runtime output intended to stay untracked.
Keep this to scaffold + docs guidance only (no validator enforcement expansion).

## ST-006 Update user-facing and scaffolded workflow path examples

Refresh README and workflow references so all progress artifact examples point to
`.engineeringagent/progress/...` and reflect lazy creation semantics.

## ST-007 Run full repository verification for path migration

Execute full validation and iteration-end checks to confirm path migration is complete,
deterministic, and consistent across CLI/runtime/docs/tests.
