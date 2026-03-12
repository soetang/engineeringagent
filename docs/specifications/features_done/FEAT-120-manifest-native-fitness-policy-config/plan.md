---
plan_id: FEAT-120
feature_id: FEAT-120
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend manifest and runtime contracts with optional config_file
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_manifest_contract.py tests/fitness/test_fitness_manifest.py
    tests/fitness/test_fitness_registry.py
- id: ST-002
  title: Add command-adapter config-file injection contract
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py
- id: ST-003
  title: Surface config-file metadata in catalog markdown and json output
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py tests/cli/test_cli_checks_catalog.py
- id: ST-004
  title: Migrate Ruff suppression rule to YAML policy config
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py
  - uv run python harness/fitness_functions/check_non_ignorable_ruff_suppressions.py
    --config-file harness/fitness_functions/policies/no_non_ignorable_ruff_suppressions.yaml
- id: ST-005
  title: Rename subprocess semgrep YAML to policy-oriented file name
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
  - uv run python harness/fitness_functions/check_loop_subprocess_boundary.py --config-file
    harness/fitness_functions/policies/loop_subprocess_boundary_semgrep_policy.yaml
- id: ST-006
  title: Regenerate docs and validate repository contracts
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run engineeringagent validate
- id: ST-007
  title: Apply reviewer feedback for Ruff policy error-path consistency
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py -k "missing_blocked_ids_error
    or surfaces_yaml_parse_errors"
  - uv run pytest -q tests/fitness/test_fitness_manifest.py
  - uv run engineeringagent validate
- id: ST-008
  title: Archive FEAT-120 after final reviewer sign-off
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-009
  title: Apply reviewer feedback for manifest/runtime helper deduplication
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_registry.py tests/fitness/test_fitness_adapters.py
  - uv run engineeringagent validate
- id: ST-010
  title: Apply reviewer warning simplifications from feature-done pass
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_registry.py tests/fitness/test_fitness_adapters.py
  - uv run engineeringagent validate
- id: ST-011
  title: Apply reviewer feedback for behavior-focused policy and catalog tests
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py tests/fitness/test_fitness_catalog_generation.py
    tests/cli/test_cli_checks_catalog.py
  - uv run engineeringagent validate
- id: ST-012
  title: Apply reviewer warning simplifications for registry path resolution and policy
    fixture writing
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_registry.py tests/fitness/test_fitness_adapters.py
  - uv run engineeringagent validate
- id: ST-013
  title: Apply reviewer warning simplifications for Ruff policy flow and catalog fixture
    deduplication
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py tests/cli/test_cli_checks_catalog.py
    tests/fitness/test_fitness_adapters.py -k "non_ignorable_suppression_adapter_surfaces_yaml_parse_errors
    or non_ignorable_suppression_adapter_surfaces_missing_blocked_ids_error or fitness_catalog"
  - uv run engineeringagent validate
- id: ST-014
  title: Apply reviewer feedback for explicit markdown catalog invariants
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py tests/cli/test_cli_checks_catalog.py
  - uv run engineeringagent validate
- id: ST-015
  title: Improve markdown catalog discoverability with config-file summary column
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py
  - uv run engineeringagent validate
- id: ST-016
  title: Fix pylint gate failures from shared test helper scaffolding
  status: done
  verification:
  - uv run pylint --score=n --reports=n src/engineeringagent tests harness
- id: ST-017
  title: Resolve pytest gate regression in repository backend-default assertions
  status: done
  verification:
  - uv run pytest -q
- id: ST-018
  title: Apply reviewer warning simplification for Ruff policy loader flow
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_adapters.py -k "missing_blocked_ids_error
    or surfaces_yaml_parse_errors"
  - uv run engineeringagent validate
- id: ST-019
  title: Apply reviewer feedback to reduce markdown assertion brittleness
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py tests/cli/test_cli_checks_catalog.py
  - uv run engineeringagent validate
- id: ST-020
  title: Close reviewer loop and archive FEAT-120
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-021
  title: Apply reviewer feedback to narrow markdown catalog assertions
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py tests/cli/test_cli_checks_catalog.py
  - uv run engineeringagent validate
- id: ST-022
  title: Request reviewer re-check for markdown assertion scope change
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-023
  title: Apply reviewer feedback for generated catalog drift guard and regeneration
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_catalog_docs_sync.py
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run engineeringagent validate
- id: ST-024
  title: Request reviewer re-check for catalog-doc drift guard closure
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend manifest and runtime contracts with optional config_file

Add `config_file` support in fitness manifest schema/models and registry rule definitions with deterministic resolution semantics.

## ST-002 Add command-adapter config-file injection contract

Update command adapter execution to pass `--config-file <path>` when the rule definition includes `config_file`, without affecting rules that omit it.

## ST-003 Surface config-file metadata in catalog markdown and json output

Update catalog serializers/renderers so generated outputs include each rule's config-file path for discoverability and operator navigation.

## ST-004 Migrate Ruff suppression rule to YAML policy config

Add `harness/fitness_functions/policies/no_non_ignorable_ruff_suppressions.yaml`, teach checker to load it via `--config-file`, and simplify manifest command entry.

## ST-005 Rename subprocess semgrep YAML to policy-oriented file name

Rename loop subprocess semgrep asset into the policy directory with policy naming, and wire checker loading through `--config-file` while preserving findings.

## ST-006 Regenerate docs and validate repository contracts

Regenerate fitness catalog docs and confirm full spec/fitness/check contracts remain valid after config-file migration.

## ST-007 Apply reviewer feedback for Ruff policy error-path consistency

Preserve policy-validation errors when config-defined rule_id is used and clean up touched test fixture formatting for maintainability.

## ST-008 Archive FEAT-120 after final reviewer sign-off

Move completed spec to docs/spec/features_done once reviewer feedback cycle is fully closed.

## ST-009 Apply reviewer feedback for manifest/runtime helper deduplication

Extract shared manifest materialization flow, centralize Ruff runtime policy resolution precedence, and reuse CLI-definition test fixtures for maintainability.

## ST-010 Apply reviewer warning simplifications from feature-done pass

Remove one-use registry materialization indirection and centralize repeated non-ignorable Ruff policy fixture setup in adapters tests.

## ST-011 Apply reviewer feedback for behavior-focused policy and catalog tests

Remove private-internal call-count assertions from Ruff policy tests and keep markdown catalog tests as smoke checks while preserving config_file contract coverage in JSON catalog assertions.

## ST-012 Apply reviewer warning simplifications for registry path resolution and policy fixture writing

Pre-resolve manifest/project paths once per manifest load and simplify Ruff policy test fixture generation via yaml.safe_dump.

## ST-013 Apply reviewer warning simplifications for Ruff policy flow and catalog fixture deduplication

Make fallback-versus-resolved Ruff policy rule_id error handling explicit and extract a shared shell-contract manifest writer in catalog generation tests.

## ST-014 Apply reviewer feedback for explicit markdown catalog invariants

Replace weakened markdown smoke assertions with explicit deterministic catalog invariants and restore no-trailing-newline contract coverage at the renderer layer.

## ST-015 Improve markdown catalog discoverability with config-file summary column

Add config-file visibility to the Active Rules markdown summary table so operators can locate policy files without scanning per-rule detail blocks.

## ST-016 Fix pylint gate failures from shared test helper scaffolding

Resolve trailing-newline and missing-docstring violations introduced with test helper package files so reviewer gate reruns pass deterministically.

## ST-017 Resolve pytest gate regression in repository backend-default assertions

Align repository backend-default test expectations with the current opencode config baseline and add focused config fallback coverage so the global pytest+coverage gate clears deterministically.

## ST-018 Apply reviewer warning simplification for Ruff policy loader flow

Inline config-file ValueError handling into runtime-policy resolution and remove the one-use loader wrapper while preserving rule_id error attribution.

## ST-019 Apply reviewer feedback to reduce markdown assertion brittleness

Keep markdown assertions limited to discoverability invariants and CLI write smoke behavior while relying on JSON catalog tests for field-level contract guarantees.

## ST-020 Close reviewer loop and archive FEAT-120

Request reviewer re-check after ST-019 and archive the spec under features_done once sign-off is received.

## ST-021 Apply reviewer feedback to narrow markdown catalog assertions

Trim markdown assertions in catalog-generation tests to the minimal FEAT-120 discoverability signal (configured policy path surfaced), while JSON assertions retain field-level contract coverage.

## ST-022 Request reviewer re-check for markdown assertion scope change

Run reviewer pass focused on FEAT-120 test scope after narrowing markdown assertions to discoverability-only coverage.

## ST-023 Apply reviewer feedback for generated catalog drift guard and regeneration

Regenerate docs/fitness-functions/rules.md from the current catalog renderer, and add a deterministic fitness rule that fails when committed markdown drifts from `engineeringagent checks catalog --format markdown` output.

## ST-024 Request reviewer re-check for catalog-doc drift guard closure

Request feature-done reviewer re-check after adding the deterministic catalog-doc sync fitness rule and regenerating docs/fitness-functions/rules.md.
