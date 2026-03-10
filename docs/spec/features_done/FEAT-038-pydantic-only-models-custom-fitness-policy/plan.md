---
plan_id: FEAT-038
feature_id: FEAT-038
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Inventory and map all dataclasses usage in src/engineeringagent for migration
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py
  - uv run pytest -q tests/test_fitness_registry.py
- id: ST-002
  title: Migrate scoped dataclass models to Pydantic v2 BaseModel
  status: done
  verification:
  - uv run pytest -q
  - uv run pyright src/engineeringagent tests harness
- id: ST-003
  title: Add custom no-stdlib-dataclasses fitness checker script under harness
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_adapters.py
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-004
  title: Register custom rule_id architecture.no-stdlib-dataclasses-in-src in harness
    manifest
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_manifest.py
  - uv run python -m engineeringagent.cli fitness list
- id: ST-005
  title: Regenerate fitness catalog docs and validate gate enforcement
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uvx --from . engineeringagent gates run --profile loop_fast
  - uvx --from . engineeringagent gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Inventory and map all dataclasses usage in src/engineeringagent for migration

Identify every stdlib dataclass and dataclasses usage in scoped source files and define target Pydantic BaseModel replacements before guardrail activation.

Notes:
- Inventory complete (scope: src/engineeringagent): loop_runtime/iteration.py (IterationPipelineDependencies), loop_runtime/phases.py (GatePhaseDependencies, CompletionPhaseDependencies, VerificationPhaseDependencies), loop_runtime/models.py (IterationOutcome, InitialFeatureLoadOutcome, PostImplementFeatureOutcome, ImplementStepInputs, FeatureIterationInputs, GatePhaseOutcome, VerificationPhaseOutcome, CompletionCommitOutcome, IterationTelemetryInputs), loop_runtime/presentation.py (RunOutputPresenter), fitness/registry.py (FitnessRuleDefinition + dataclasses.replace usage), fitness/runner.py (FitnessRunSummary), opencode_permissions.py (PermissionProbeResult), specs.py (ValidationIssue).
- Migration map: replace stdlib dataclass patterns with Pydantic v2 BaseModel in each listed module; use ConfigDict(frozen=True, extra="forbid") for current frozen dataclasses; replace dataclasses.replace(...) in fitness/registry.py with BaseModel model_copy(update=...).

## ST-002 Migrate scoped dataclass models to Pydantic v2 BaseModel

Refactor source models in src/engineeringagent from stdlib dataclasses to BaseModel, preserving behavior and call-site compatibility where practical.

Notes:
- Migrated PermissionProbeResult in src/engineeringagent/opencode_permissions.py from stdlib dataclass to frozen Pydantic BaseModel.
- Migrated FitnessRunSummary in src/engineeringagent/fitness/runner.py from stdlib dataclass to frozen Pydantic BaseModel.
- Migrated ValidationIssue in src/engineeringagent/specs.py from stdlib dataclass to Pydantic BaseModel to keep spec-validation issue records on the unified model contract.
- Migrated FitnessRuleDefinition in src/engineeringagent/fitness/registry.py from stdlib dataclass to frozen Pydantic BaseModel and replaced dataclasses.replace(...) cloning with model_copy(update=...).
- Migrated RunOutputPresenter in src/engineeringagent/loop_runtime/presentation.py from frozen stdlib dataclass to frozen Pydantic BaseModel.
- Migrated IterationPipelineDependencies in src/engineeringagent/loop_runtime/iteration.py from frozen stdlib dataclass to frozen Pydantic BaseModel.
- Migrated GatePhaseDependencies, CompletionPhaseDependencies, and VerificationPhaseDependencies in src/engineeringagent/loop_runtime/phases.py from frozen stdlib dataclasses to frozen Pydantic BaseModel.
- Migrated all remaining loop runtime data models in src/engineeringagent/loop_runtime/models.py (IterationOutcome, InitialFeatureLoadOutcome, PostImplementFeatureOutcome, ImplementStepInputs, FeatureIterationInputs, GatePhaseOutcome, VerificationPhaseOutcome, CompletionCommitOutcome, IterationTelemetryInputs) from frozen stdlib dataclasses to frozen Pydantic BaseModel.

## ST-003 Add custom no-stdlib-dataclasses fitness checker script under harness

Implement command-backed checker script in harness/fitness-functions that scans only src/engineeringagent and returns deterministic machine-readable violations.

Notes:
- Added harness/fitness-functions/check_no_stdlib_dataclasses_in_src.py to scan only src/engineeringagent/**/*.py with AST-based detection.
- Checker emits deterministic JSON envelope for rule_id architecture.no-stdlib-dataclasses-in-src, failing on stdlib dataclasses imports, dataclass decorators, and dataclasses namespace usage.

## ST-004 Register custom rule_id architecture.no-stdlib-dataclasses-in-src in harness manifest

Declare the new command rule in harness/fitness-functions/rules.yaml with rule_id architecture.no-stdlib-dataclasses-in-src, severity error, scope, rationale, and remediation text recommending BaseModel.

Notes:
- Registered architecture.no-stdlib-dataclasses-in-src as a command-backed custom error rule in harness/fitness-functions/rules.yaml with scope src/engineeringagent and remediation to migrate to pydantic.BaseModel.

## ST-005 Regenerate fitness catalog docs and validate gate enforcement

Ensure rule appears in generated catalog and gate profiles fail on violations while passing on compliant source.

Notes:
- Regenerated docs/fitness-functions/rules.md via fitness catalog command.
- Verified loop_fast and precommit profiles both pass with architecture.no-stdlib-dataclasses-in-src active.
