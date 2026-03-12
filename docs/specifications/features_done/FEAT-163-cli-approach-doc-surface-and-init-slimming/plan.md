---
plan_id: FEAT-163
feature_id: FEAT-163
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define approach information architecture and stable topic ids
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-002
  title: Add frontmatter metadata contract for guidance source docs
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py
- id: ST-003
  title: Implement approach registry and packaged docs resource loading
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py
  - python -m build
- id: ST-004
  title: Add CLI approach command surface with list show output behavior
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
  - uv run pytest -q tests/cli/test_cli_typer_parity_helpers.py
- id: ST-005
  title: Slim init scaffold to operational essentials and AGENTS bootstrap patch
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_scaffold.py
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-006
  title: Retire scaffold-doc fitness rules scripts and related tests
  status: done
  verification:
  - uv run pytest -q tests/fitness
  - uv run pytest -q tests/meta/test_test_layout_fitness_topic.py
- id: ST-007
  title: Update AGENTS docs-map validator contract for approach bootstrap
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-008
  title: Update agent-facing docs and regenerate fitness catalog docs
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run pytest -q tests/fitness/test_fitness_rules_catalog_docs_sync.py
- id: ST-009
  title: Run full quality gates for feature completion
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q
  - uv run ruff check src tests harness
  - uv run pyright src/engineeringagent tests harness
- id: ST-010
  title: Enforce modular boundaries for approach architecture
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-011
  title: Apply code simplifier clarity refactors to init and init-scaffold plumbing
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-012
  title: Harden approach CLI and validator tests against contract wording drift
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
  - uv run pytest -q tests/cli/test_approach_registry.py
  - uv run pytest -q tests/meta/test_validator.py
- id: ST-013
  title: Enforce launcher-neutral approach docs and installed-package resource proof
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py::test_approach_docs_are_packaged_resources
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/cli/test_approach_registry.py
- id: ST-014
  title: Harden approach tests against registry-output coupling and topic formatting
    drift
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-015
  title: Remove self-referential AGENTS bootstrap fixtures and gate packaging checks
  status: done
  verification:
  - uv run pytest -q tests/cli/test_approach_registry.py::test_approach_docs_are_packaged_resources
  - uv run pytest -q tests/cli/test_init_command.py::test_scaffold_agents_bootstrap_matches_approach_fixture
  - uv run pytest -q tests/cli/test_cli.py::test_main_approach_commands_render_expected_markdown
  - uv run pytest -q tests/meta/test_validator.py::test_validate_accepts_agents_bootstrap_contract_when_complete
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/cli/test_cli.py::test_validate_fails_on_agents_bootstrap_contract_errors
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define approach information architecture and stable topic ids

Finalize canonical ids and aliases with a progressive disclosure model that starts
from an overview and drills into specific guidance, without rewriting migrated doc
bodies beyond the allowed migration edits. Include rationale for id/alias choices
and source-to-topic mapping notes.

## ST-002 Add frontmatter metadata contract for guidance source docs

Add `approach_id` to each selected guidance markdown source document and enforce
deterministic parsing constraints (single id, unique ids, required H1 title)
while preserving source prose aside from allowed migration edits.

## ST-003 Implement approach registry and packaged docs resource loading

Introduce a registry module that discovers packaged approach docs, validates
metadata, and returns deterministic list/show payloads for CLI handlers.
Ensure package build artifacts include approach docs resources.

## ST-004 Add CLI approach command surface with list show output behavior

Extend Typer/CLI handlers with `approach`, `approach list`, and `approach <topic_id>`
semantics plus optional `--output` file writing and deterministic input errors.

## ST-005 Slim init scaffold to operational essentials and AGENTS bootstrap patch

Remove user guidance markdown scaffolding from init manifests and align init output,
counters, and tests. Keep AGENTS handling modes but switch scaffold guidance to a
deterministic 1-3 sentence approach bootstrap snippet that also declares launcher
preference separately from approach doc command examples. Remove baseline scaffold
creation of `docs/spec/potential_features.yaml`.

## ST-006 Retire scaffold-doc fitness rules scripts and related tests

Remove doc-sync/link/allowlist fitness rule entries, delete obsolete scripts/tests,
and update layout guard tests that enumerate expected fitness test locations.

## ST-007 Update AGENTS docs-map validator contract for approach bootstrap

Replace or retire validator assumptions that require docs/* file references in the
Documentation Layout Reference section. Add deterministic validation coverage for
the new bootstrap contract.

## ST-008 Update agent-facing docs and regenerate fitness catalog docs

Update agent-facing guidance references to use `engineeringagent approach` commands
without making README a user redirect target for approach.
Regenerate `docs/fitness-functions/rules.md` after manifest updates and keep sync tests green.

## ST-009 Run full quality gates for feature completion

Run repository validation and core quality gates to confirm the new docs delivery
model and init simplification are stable.

## ST-010 Enforce modular boundaries for approach architecture

Implement and verify explicit separation between CLI routing, approach metadata/content
handling, and init scaffold responsibilities. Ensure AGENTS bootstrap text has one
canonical producer and avoid duplicated parsing/rendering logic across layers.

## ST-011 Apply code simplifier clarity refactors to init and init-scaffold plumbing

Refactor init backend resolution helpers, extract init request/dependencies builders, and simplify precommit template/config helper shape for reduced control-flow nesting and mutation noise.
Keep runtime behavior and user-facing output/error text unchanged.

## ST-012 Harden approach CLI and validator tests against contract wording drift

Reduce brittle test assertions by validating CLI user-visible behavior and bootstrap diagnostics by contract shape instead of internal handler args or exact line numbers.
Keep command outputs stable while minimizing maintenance risk from prose edits.

## ST-013 Enforce launcher-neutral approach docs and installed-package resource proof

Replace launcher-specific commands in canonical approach documents with launcher-neutral `engineeringagent ...` examples, and add a focused test that asserts approach docs are loadable through package resources via `importlib.resources.files("engineeringagent.approach").joinpath("docs")` with a known topic round-trip.

## ST-014 Harden approach tests against registry-output coupling and topic formatting drift

Replace registry-derived test fixture expectations with explicit topic matrix constants and ensure assertions validate IDs/order and alias coverage without binding to formatted topic titles.

## ST-015 Remove self-referential AGENTS bootstrap fixtures and gate packaging checks

Replace tests reading bootstrap expectation from production template path with an immutable fixture and gate heavy packaging assertions behind integration tooling checks plus explicit skip behavior when build execution is unavailable.
