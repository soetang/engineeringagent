---
plan_id: FEAT-184
feature_id: FEAT-184
status: backlog
source_spec: spec.yaml
source_research: research.md
planning_tier: researched
phases:
  - id: P1
    title: Delete high-confidence meta and fitness whole-file candidates
    status: backlog
    verification:
      - uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave1_cleanup.py
      - uv run pytest -q tests/meta/test_validator.py
      - uv run pytest -q tests/checks/test_run_checks_contract_loader.py
      - uv run pytest -q tests/config/test_config_agents_backend.py tests/agents/test_opencode_backend.py
      - uv run pytest -q tests/fitness
  - id: P2
    title: Remove helper-coverage padding and preserve only behavior-facing coverage
    status: backlog
    verification:
      - uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave2_anchor_coverage.py
      - uv run pytest -q tests/cli/test_cli.py
      - uv run pytest -q tests/config/test_config_agents_backend.py tests/agents/test_opencode_backend.py tests/agents/test_codex_backend.py
      - uv run pytest -q tests/git/test_client.py tests/git/test_git_client.py
      - uv run pytest -q tests/loop/test_loop_feature_iteration_execution.py tests/loop/test_loop_feature_iteration_verification.py
  - id: P3
    title: Trim mixed loop presentation tests and delete dead test support
    status: backlog
    verification:
      - uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave3_loop_trim.py
      - uv run pytest -q tests/loop/test_loop_selection.py tests/loop/test_loop_output.py
      - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_reviewers.py tests/loop/test_loop_opencode_integration.py
  - id: P4
    title: Prove full-suite and coverage-gate stability after cleanup
    status: backlog
    verification:
      - uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_cleanup_summary.py
      - uv run pytest -q
      - uv run engineeringagent checks run --phase feature_done
---

# FEAT-184 Plan

## Objective

- Delete low-value, brittle, and implementation-coupled tests first from `tests/meta` and `tests/fitness`, then from helper-heavy loop surfaces, while keeping the repository on the current full-suite `pytest` path and the existing `--cov-fail-under=95` gate.

## Architecture and Approach

- Treat this feature as a test-suite composition cleanup, not a production-code feature. The implementation shape is an ordered deletion program: remove whole files where the suite only guards deleted paths, repository wording, layout mirroring, or checker internals; keep only the smallest replacement coverage needed to protect real user-visible behavior.
- Prefer feature-owned verification scripts under `docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/` for one-off cleanup assertions such as candidate inventories, deleted-path absence, or retained-anchor audits. Do not add fresh permanent unit tests unless a truly behavior-facing gap remains after deletions.
- Keep behavior-facing anchors as the stability boundary: CLI command behavior in `tests/cli/test_cli.py:53`, checks runtime loading in `tests/checks/test_run_checks_contract_loader.py:14`, validator contract coverage in `tests/meta/test_validator.py:30`, loop lifecycle/execution/reviewer flow in `tests/loop/test_loop_feature_iteration_lifecycle.py:33`, `tests/loop/test_loop_feature_iteration_execution.py:32`, `tests/loop/test_loop_feature_iteration_verification.py:36`, `tests/loop/test_loop_reviewers.py:18`, and git behavior in `tests/git/test_client.py:9` and `tests/git/test_git_client.py:18`.
- Use wave ordering from the research: delete high-confidence whole-file `meta` and `fitness` candidates first, then remove branch-padding helper bundles, then trim mixed loop presentation assertions only after the retained loop-flow anchors are proving the workflow end to end.
- Preserve the coverage contract as an invariant owned by `pyproject.toml:26` and locked by `tests/meta/test_validator.py:1781`. If deleting brittle tests drops coverage for still-important modules, first try to prove the cleanup with supporting scripts plus retained anchor suites; only add a new regression test if an actual behavior-facing contract is otherwise left uncovered.
- Keep backend-oriented anchors explicit in the retained set: backend configuration coverage in `tests/config/test_config_agents_backend.py:24`, backend adapter behavior in `tests/agents/test_opencode_backend.py` and `tests/agents/test_codex_backend.py`, and loop/backend integration coverage in `tests/loop/test_loop_opencode_integration.py:33` remain outside the first-wave deletion set.

```bash
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_deleted_test_inventory.py
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_retained_anchor_suites.py
```

## Interfaces and Impacted Surfaces

- `pyproject.toml:26` - pytest addopts keep the repository-wide `--cov=engineeringagent --cov-fail-under=95 -n 2` contract unchanged.
- `harness/checks.yaml:30` - repo checks still run `uv run pytest -q`, so cleanup must hold on a normal full-suite execution path.
- `tests/meta/test_validator.py:1781` - retains the meta-level coverage-gate contract and should remain a guardrail even if many other `tests/meta` files are deleted.
- `tests/meta/test_legacy_shim_imports.py:9`, `tests/meta/test_no_gate_profile_references.py:18`, `tests/meta/test_legacy_checks_import_guard.py:15`, `tests/meta/test_agent_boundary_guards.py:39`, `tests/meta/test_agent_boundary_migration_smoke.py:114`, `tests/specs/test_specs_layout_smoke.py:23` - first-wave whole-file deletion candidates centered on removed paths, wording, AST policing, and repo layout.
- `tests/meta/test_spec_writing_reference_doc.py:71`, `tests/meta/test_spec_writing_reference_doc.py:202` - explicitly mixed file: preserve only the verification-command extraction behavior if coverage needs it, otherwise delete the whole file with the wording-sync section.
- `tests/fitness/test_fitness_rules_repo_validators_boundary.py:6`, `tests/fitness/test_fitness_rules_test_layout_module_mirroring.py:56`, `tests/fitness/test_fitness_rules_no_doc_content_tests.py:40`, `tests/fitness/test_fitness_rules_source_first_loop_commands.py:72`, `tests/fitness/test_fitness_rules_harness_src_import_allowlist.py:29`, `tests/fitness/test_fitness_rules_scaffold_template_locality.py:35` - first-wave checker self-tests whose contracts are internal repository policy rather than user-visible runtime behavior.
- `tests/meta/test_coverage_threshold_regressions.py:67`, `tests/meta/test_coverage_threshold_regressions.py:873`, `tests/meta/test_coverage_misc.py:32` - broad helper-coverage padding files that should be deleted or sharply replaced only if retained production behavior still needs behavior-facing proof.
- `tests/loop/test_loop_feature_iteration_support.py:14`, `tests/loop/test_feature_iteration_feedback_support.py:19`, `tests/loop/test_loop_feature_phase_progress_helpers.py:15`, `tests/loop/test_selected_feature_load_without_archive_fallback.py:11`, `tests/loop/test_loop_selection.py:120`, `tests/loop/test_loop_output.py:1108` - lower-value loop surfaces to trim after anchor suites stay green.
- `tests/config/test_config_agents_backend.py:24`, `tests/agents/test_opencode_backend.py`, `tests/agents/test_codex_backend.py`, `tests/loop/test_loop_opencode_integration.py:33` - backend-facing anchors that should remain available while low-value test surfaces are deleted.
- `tests/loop/feature_iteration_feedback_support.py:13`, `tests/loop/_feedback_envelope.py:20`, `tests/loop/feature_iteration_support.py:28` - test-only helpers that may become dead or simplifiable after loop-surface deletions.
- `docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/` - preferred home for feature-scoped verification scripts that check deletion inventory, retained anchors, and cleanup completeness without adding new long-lived tests.

## Refactoring Strategy

- Prefer file deletion over test rewriting for pure migration, wording, and repository-shape suites.
- Separate cleanup into deletion waves so the repository never loses both the brittle file and the anchor replacement at the same time.
- Keep shared loop support helpers until the end; many retained loop anchors still import them, so delete support files only after confirming remaining imports and assertions no longer need them.
- Use supporting scripts for temporary feature-specific checks, and use the full suite after each wave to detect coverage regressions early. If a surviving production surface still lacks meaningful coverage, add or retain the narrowest behavior-facing regression near the anchor suite that already owns that workflow.

## Phase Plan

### Phase 1: Delete high-confidence meta and fitness whole-file candidates

- Goal: remove the largest set of low-value files that only protect deleted paths, exact repository wording, mirrored layout, or checker internals.
- Areas touched: `tests/meta/`, `tests/fitness/`, `tests/specs/test_specs_layout_smoke.py`, and any now-unused test fixtures or imports referenced only by those files.
- Interfaces:
  - Delete first-wave `tests/meta` migration and boundary guards documented in `research.md`.
  - Delete the wording-lock portion of `tests/meta/test_spec_writing_reference_doc.py`; if coverage requires retention, keep only the verification-command extraction behavior and move that proof into a smaller behavior-adjacent test.
  - Delete first-wave `tests/fitness` rule self-tests that only validate repo-policy and checker internals.
  - Keep `tests/meta/test_validator.py` as the retained meta anchor because it still validates real repository contracts, including the coverage gate.
- Refactoring: remove imports, fixtures, and helper references that become dead when the deleted files disappear, but avoid reshaping production code.
- Verification:
  - `uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave1_cleanup.py`
  - `uv run pytest -q tests/meta/test_validator.py`
  - `uv run pytest -q tests/checks/test_run_checks_contract_loader.py`
  - `uv run pytest -q tests/config/test_config_agents_backend.py tests/agents/test_opencode_backend.py`
  - `uv run pytest -q tests/fitness`
- Example verification design:

```python
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    assert not (repo / "tests/meta/test_legacy_shim_imports.py").exists()
    assert not (repo / "tests/fitness/test_fitness_rules_repo_validators_boundary.py").exists()
    return 0
```

- Documentation changes: update `docs/specifications/features/FEAT-184-delete-low-value-tests/research.md`, `docs/specifications/features/FEAT-184-delete-low-value-tests/plan.md`, and any feature-owned supporting scripts if the actual deleted-file set differs from the current first-wave inventory.

### Phase 2: Remove helper-coverage padding and preserve only behavior-facing coverage

- Goal: delete the broad branch-padding bundles and replace any truly necessary lost coverage with behavior-facing regressions in existing anchor suites.
- Areas touched: `tests/meta/test_coverage_threshold_regressions.py`, `tests/meta/test_coverage_misc.py`, likely retained anchors under `tests/cli/`, `tests/git/`, `tests/checks/`, and loop lifecycle files.
- Interfaces:
  - Delete direct tests of private helpers and internal normalization branches.
  - If a coverage loss affects code that still matters, shift the proof into existing external-contract suites such as `tests/cli/test_cli.py`, `tests/checks/test_run_checks_contract_loader.py`, `tests/config/test_config_agents_backend.py`, backend adapter tests, or loop lifecycle/execution tests.
- Refactoring: collapse now-redundant helper fixtures and avoid preserving helper-specific assertion utilities that only existed for the deleted bundles.
- Verification:
  - `uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave2_anchor_coverage.py`
  - `uv run pytest -q tests/cli/test_cli.py`
  - `uv run pytest -q tests/config/test_config_agents_backend.py tests/agents/test_opencode_backend.py tests/agents/test_codex_backend.py`
  - `uv run pytest -q tests/git/test_client.py tests/git/test_git_client.py`
  - `uv run pytest -q tests/loop/test_loop_feature_iteration_execution.py tests/loop/test_loop_feature_iteration_verification.py`
- Example verification design:

```python
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    text = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "--cov-fail-under=95" in text
    return 0
```

- Documentation changes: record any intentional coverage replacements in `docs/specifications/features/FEAT-184-delete-low-value-tests/research.md` and prefer feature-owned supporting scripts over new permanent tests when the verification need is specific to this cleanup wave.

### Phase 3: Trim mixed loop presentation tests and delete dead test support

- Goal: remove helper-only and presentation-coupled loop assertions while preserving loop runtime behavior coverage.
- Areas touched: `tests/loop/test_loop_feature_iteration_support.py`, `tests/loop/test_feature_iteration_feedback_support.py`, `tests/loop/test_loop_feature_phase_progress_helpers.py`, `tests/loop/test_selected_feature_load_without_archive_fallback.py`, selective cases inside `tests/loop/test_loop_selection.py` and `tests/loop/test_loop_output.py`, plus any dead test support modules.
- Interfaces:
  - Delete tests that only assert helper normalization, no-fallback private helper branches, or exact terminal label wording.
  - In `tests/loop/test_loop_selection.py`, delete the presentation-coupled cases that patch `describe_action` or `build_selector_prompt` only to assert exact step-label strings; keep fallback-selection and configured-backend behavior that changes control flow.
  - In `tests/loop/test_loop_output.py`, delete the final non-verbose rendered-text assertions for emoji/line wording while keeping persistence, reviewer-status, telemetry, and runtime-state assertions from earlier sections.
  - Preserve runtime-flow assertions in `tests/loop/test_loop_runtime_iteration.py`, `tests/loop/test_loop_feature_iteration_lifecycle.py`, `tests/loop/test_loop_feature_iteration_feedback.py`, and `tests/loop/test_loop_reviewers.py`.
  - Re-check whether `tests/loop/feature_iteration_feedback_support.py`, `tests/loop/_feedback_envelope.py`, or adjacent helper modules are still imported after the trim.
- Refactoring: move any remaining useful assertions to the owning loop-flow suite instead of keeping dedicated support-test files alive.
- Verification:
  - `uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave3_loop_trim.py`
  - `uv run pytest -q tests/loop/test_loop_selection.py tests/loop/test_loop_output.py`
  - `uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_reviewers.py tests/loop/test_loop_opencode_integration.py`
- Example verification design:

```python
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    assert not (repo / "tests/loop/test_loop_feature_iteration_support.py").exists()
    return 0
```

- Documentation changes: update `docs/specifications/features/FEAT-184-delete-low-value-tests/research.md` and the supporting verification scripts if mixed-file trims reveal dead test-support modules that were not part of the original inventory.

### Phase 4: Prove full-suite and coverage-gate stability after cleanup

- Goal: confirm the reduced suite still passes the full repository run, preserves the coverage threshold, and leaves feature artifacts aligned with the implemented cleanup scope.
- Areas touched: no new product surfaces; only the final retained test inventory and FEAT-184 artifacts if verification forces small plan/research adjustments.
- Interfaces:
  - Full repository `pytest` remains the final correctness contract.
  - `pyproject.toml:26`, `tests/meta/test_validator.py:1781`, and `harness/checks.yaml:30` remain unchanged and prove the gate was preserved rather than weakened.
- Refactoring: remove any leftover dead imports, empty helper modules, or fixture factories exposed only by deleted tests.
- Verification:
  - `uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_cleanup_summary.py`
  - `uv run pytest -q`
  - `uv run engineeringagent checks run --phase feature_done`
- Example verification design:

```bash
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_cleanup_summary.py
uv run pytest -q
uv run engineeringagent checks run --phase feature_done
```

- Documentation changes: finalize `docs/specifications/features/FEAT-184-delete-low-value-tests/research.md` and `docs/specifications/features/FEAT-184-delete-low-value-tests/plan.md` with the implemented deletion waves, retained anchors, and any coverage-driven exceptions.

## Verification Strategy

- Start each wave with a feature-owned supporting script that checks the intended deletion or retention inventory, then run targeted anchor suites so failures reveal which behavior-facing contract lost meaningful coverage.
- Run `uv run pytest -q` after every major wave, not just at the end, because FEAT-184 risk is suite-wide coverage erosion more than local assertion churn.
- Keep `tests/meta/test_validator.py:1781` as an explicit invariant check that the coverage gate stays declared while the suite shape changes.
- Use `uv run engineeringagent checks run --phase feature_done` at the end to confirm the repository still satisfies its normal quality path after the test inventory shrinks.

```bash
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave1_cleanup.py
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave2_anchor_coverage.py
uv run python docs/specifications/features/FEAT-184-delete-low-value-tests/supporting/check_wave3_loop_trim.py
```

## Documentation Changes

- Keep `docs/specifications/features/FEAT-184-delete-low-value-tests/research.md` as the source-of-truth inventory for deletion candidates, retained anchors, and any mixed-file exceptions discovered during implementation.
- Keep `docs/specifications/features/FEAT-184-delete-low-value-tests/plan.md` aligned with the actual deletion wave order, final retained anchor suites, and verification commands used for the implementation session.
- Do not broaden repository-wide docs for this feature unless deleting a brittle test exposes stale guidance about how the suite is intentionally organized.

## Risks and Notes

- The biggest execution risk is deleting helper-padding tests that currently prop up coverage for still-important modules; replace only the missing behavioral proof, not the helper-level branch matrix.
- Mixed loop files are the highest-risk trim surfaces because they contain both brittle presentation checks and real runtime-flow coverage.
- `tests/meta` and `tests/fitness` can tolerate aggressive whole-file deletion, but shared loop support modules should only be removed after import sites in retained loop anchors are rechecked.
- FEAT-184 should leave the suite smaller and more behavior-oriented, but it should not relax `pyproject.toml:26`, `tests/meta/test_validator.py:1781`, or `harness/checks.yaml:30` to get there.
