---
plan_id: FEAT-034
feature_id: FEAT-034
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Create loop_runtime package scaffold and preserve facade compatibility seams
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_does_not_include_specs_created_after_startup
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_permission_precheck_applies_only_to_default_implement_mode
- id: ST-002
  title: Extract loop dataclasses into loop_runtime models with facade re-exports
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_does_not_include_specs_created_after_startup
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_skips_permission_precheck_with_skip_implement
- id: ST-003
  title: Add facade contract tests for signature and seam stability
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-004
  title: Extract telemetry and progress-log internals into loop_runtime telemetry
    module
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_writes_per_feature_progress_log
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_telemetry_includes_log_path
- id: ST-005
  title: Extract feature state and archive lifecycle helpers into loop_runtime feature_state
    module
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_loop_archived_done_requires_same_iteration_completion_commit
- id: ST-006
  title: Extract selector and implement phase internals while preserving facade monkeypatch
    seams
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_choose_feature_with_selector_fallbacks_when_parse_fails
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_default_implement_mode_fails_on_permission_rejection_output
- id: ST-007
  title: Refactor iteration and completion phases into explicit runtime pipeline
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_retries_same_feature_until_done
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archived_done_without_completion_commit_fails
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-008
  title: Add loop facade size fitness guardrail and update directionality boundaries
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_loop_facade_line_budget_rule_configuration
  - uv run pytest -q tests/test_fitness_rules_directionality.py
  - uv run pytest -q tests/test_fitness_rules_directionality.py::test_directionality_rule_reports_blocked_loop_runtime_import
  - uv run pytest -q tests/test_fitness_rules_loop_subprocess_boundary.py
  - uv run python -c "from pathlib import Path; lines=len(Path('src/engineeringagent/loop.py').read_text(encoding='utf-8').splitlines());
    assert lines < 1436, lines; assert lines <= 650, lines; print(lines)"
- id: ST-009
  title: Run focused verification and final loop_fast validation
  status: done
  verification:
  - uv run ruff check src/engineeringagent --select PLR0913
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uv run pytest -q tests/test_fitness_rules_directionality.py tests/test_fitness_rules_prompt_locality.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Create loop_runtime package scaffold and preserve facade compatibility seams

Introduce `src/engineeringagent/loop_runtime/` and baseline module files, while retaining `src/engineeringagent/loop.py` as the compatibility facade.

## ST-002 Extract loop dataclasses into loop_runtime models with facade re-exports

Move loop dataclasses into `src/engineeringagent/loop_runtime/models.py` and re-export through `src/engineeringagent/loop.py` so test and import surfaces remain stable.

## ST-003 Add facade contract tests for signature and seam stability

Add explicit tests (for example `tests/test_loop_contracts.py`) that assert stable signatures for `run_loop`, `_run_feature_iteration`, and `run_implement_step`, confirm `engineeringagent.loop.IterationOutcome` remains importable, and verify documented seam symbols remain available for monkeypatching.

## ST-004 Extract telemetry and progress-log internals into loop_runtime telemetry module

Move run telemetry and per-feature progress-log helpers out of facade, preserving output semantics and ANSI-free persisted artifacts.

## ST-005 Extract feature state and archive lifecycle helpers into loop_runtime feature_state module

Move feature path resolution, status touching, archive fallback/load-refresh, archive/restore operations, and related state predicates to dedicated helpers. In this extraction, explicitly deduplicate repeated archived-post-implement decision branches by centralizing `PostImplementFeatureOutcome` construction logic and message selection.

## ST-006 Extract selector and implement phase internals while preserving facade monkeypatch seams

Move deterministic/selector parsing and implement engine internals into runtime modules, keeping `_choose_feature_with_selector` and `run_implement_step` stable facade seams for tests.

## ST-007 Refactor iteration and completion phases into explicit runtime pipeline

Move gate/completion internals and iteration phase logic into `loop_runtime/phases.py` and `loop_runtime/iteration.py`, keeping `_run_feature_iteration` in facade as a stable wrapper.

## ST-008 Add loop facade size fitness guardrail and update directionality boundaries

Add/enable a fitness rule that enforces a permanent max line budget for `src/engineeringagent/loop.py` and update dependency directionality checks so blocked modules cannot import `engineeringagent.loop_runtime` internals.

## ST-009 Run focused verification and final loop_fast validation

Validate extracted architecture and facade readability constraints with focused loop and fitness checks plus final gate profile used by run-loop workflows.
