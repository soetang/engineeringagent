---
plan_id: FEAT-030
feature_id: FEAT-030
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Decompose loop iteration orchestration into maintainable helper phases
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-002
  title: Harden fitness CLI metadata joins and normalize minor output wording
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py
  - uv run pytest -q tests/test_gates.py
- id: ST-003
  title: Simplify validator docs-map parsing and reduce section-coupling fragility
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
- id: ST-004
  title: Refactor subprocess allowlist handling and keep architecture policy explicit
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_loop_subprocess_boundary.py
  - uv run pytest -q tests/test_fitness_registry.py
- id: ST-005
  title: Add preventive guardrails mapped to discovered issue classes
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_catalog_generation.py
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate --schema-only
- id: ST-006
  title: Configure and enforce Ruff complexity thresholds for orchestration hotspots
  status: done
  verification:
  - uv run ruff check src/engineeringagent
  - uvx --from . engineeringagent gates run --profile precommit
- id: ST-007
  title: Run focused regressions and final loop_fast validation
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Decompose loop iteration orchestration into maintainable helper phases

Split `_run_feature_iteration` into focused helpers for feature load/recovery, implement-stage evaluation, and post-implement reconciliation. Keep behavior stable.

Notes:
- Example target: src/engineeringagent/loop.py::_run_feature_iteration (current anchor from code-simplifier analysis around line ~628).
- Example extraction: isolate load/recovery decisions (feature missing, loaded from archive, load errors) into one helper that returns structured state instead of repeated branch chains.
- Example extraction: isolate post-implement reconciliation (re-load feature state, archive mismatch handling) into one helper to reduce duplicate message-building.

## ST-002 Harden fitness CLI metadata joins and normalize minor output wording

Remove brittle dictionary lookups in fitness JSON shaping and apply minor wording normalization where it improves consistency and resilience.

Notes:
- Example target: src/engineeringagent/cli.py::cmd_fitness_run (code-simplifier anchor around line ~247).
- Example hardening: replace direct remediation map indexing with safe lookup plus deterministic fallback text when catalog/result skew occurs.
- Example wording cleanup: normalize repeated hint/failure wording for consistency while preserving command semantics and JSON envelope shape.

## ST-003 Simplify validator docs-map parsing and reduce section-coupling fragility

Refactor docs-map extraction logic to avoid dependence on a hard-coded section ordinal while preserving scoped extraction and deterministic errors.

Notes:
- Example target: src/engineeringagent/validator.py::_iter_agents_docs_map_references (code-simplifier anchor around line ~157).
- Example parser change: match section heading by semantic text and number pattern (for example, ## <n>) instead of exact hard-coded ordinal value.
- Example simplification: use enumerate(..., start=1) plus dedicated token extraction helper to avoid manual line-offset arithmetic.

## ST-004 Refactor subprocess allowlist handling and keep architecture policy explicit

Reduce drift risk in subprocess allowlist wiring and keep policy intent auditable. Add or update tests to lock in allowed and disallowed boundaries.

Notes:
- Example target: src/engineeringagent/fitness/builtin_rules.py::_SUBPROCESS_ALLOWLIST and _subprocess_call_violations (code-simplifier anchors around lines ~36 and ~144).
- Example maintainability change: derive allowlist paths from module references where practical to reduce string-path drift during file moves.
- Example decomposition: split alias collection and violation scanning into focused helpers to reduce mixed responsibilities in one function.

## ST-005 Add preventive guardrails mapped to discovered issue classes

For each high-value refactor class, document and implement whether prevention should live in fitness checks, validator checks, Ruff linting, or a combination.

Notes:
- Example mapping: loop orchestration complexity -> Ruff rules C901/PLR0912/PLR0915 with repository thresholds.
- Example mapping: fitness catalog/result metadata skew -> validator or runtime integrity check with deterministic diagnostic instead of KeyError-style failure.
- Example mapping: docs-map extraction fragility -> validator guard that fails when docs-map section exists but extraction returns unexpected empty references.

## ST-006 Configure and enforce Ruff complexity thresholds for orchestration hotspots

Enable and tune C901, PLR0912, and PLR0915 thresholds in project Ruff configuration to surface maintainability regressions with acceptable noise.

Notes:
- Example config area: pyproject.toml [tool.ruff.lint] with explicit selection/extension of C901, PLR0912, and PLR0915.
- Example tuning controls: lint.mccabe.max-complexity, lint.pylint.max-branches, lint.pylint.max-statements.
- Example calibration strategy: start with current codebase baseline, set thresholds to catch new complexity growth, and adjust only with justified false-positive review.

## ST-007 Run focused regressions and final loop_fast validation

Confirm no behavioral regression across touched surfaces and verify final gate profile expected by loop execution.
