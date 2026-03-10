---
plan_id: FEAT-171
feature_id: FEAT-171
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove AGENTS docs-map validator from validate composition
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
- id: ST-002
  title: Retire AGENTS bootstrap validator module and direct unit tests
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
- id: ST-003
  title: Update CLI validate assertions for AGENTS-permissive behavior
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-004
  title: Remove repo-validators boundary fitness rule and references
  status: done
  verification:
  - uv run pytest -q tests/fitness
- id: ST-005
  title: Regenerate fitness catalog documentation
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
- id: ST-006
  title: Run targeted validate regression checks
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run engineeringagent validate
- id: ST-007
  title: Remove retired docs-map issue code mappings
  status: done
  verification:
  - uv run pytest -q tests/checks/test_validate_entrypoint_registry.py
- id: ST-008
  title: Decouple remaining FEAT-171 tests from retired AGENTS/docs-map wording
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py tests/checks/test_validate_entrypoint_registry.py
    tests/fitness/test_fitness_rules_repo_validators_boundary.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove AGENTS docs-map validator from validate composition

Update repo validator composition to stop producing AGENTS bootstrap issues
during validate execution, including schema-only mode.

## ST-002 Retire AGENTS bootstrap validator module and direct unit tests

Remove or deprecate `repo_policy_docs_map` functionality and eliminate
test coverage that enforces AGENTS bootstrap-line presence.

## ST-003 Update CLI validate assertions for AGENTS-permissive behavior

Adjust CLI tests so AGENTS.md content is not treated as a validation contract
and validate output only reflects remaining active validators.

## ST-004 Remove repo-validators boundary fitness rule and references

Remove `architecture.repo-validators-boundary` from fitness manifest/catalog,
delete its checker script, and delete or replace tests that hardcode specific
validator import/function requirements.

## ST-005 Regenerate fitness catalog documentation

Regenerate `docs/fitness-functions/rules.md` so published rule inventory matches
manifest changes after removing the repo-validators boundary rule.

## ST-006 Run targeted validate regression checks

Execute targeted checks to verify AGENTS.md freedom while preserving all
other validate behavior.

## ST-007 Remove retired docs-map issue code mappings

Eliminate stale docs-map semantic code mapping entries from repo validator
issue-code projection so retired AGENTS/docs-map contract logic cannot leak into
future validation semantics.

## ST-008 Decouple remaining FEAT-171 tests from retired AGENTS/docs-map wording

Simplify lingering test fixtures/assertions so validator coverage remains
behavior-focused without relying on retired AGENTS bootstrap constants or docs-map
wording.
