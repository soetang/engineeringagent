---
date: 2026-03-10T09:24:33+00:00
researcher: OpenCode
git_commit: 01e9b71
branch: master
repository: engineeringagent
topic: "Implementation research for FEAT-183 remove flat-spec compatibility"
tags: [research, codebase, specs, approach, reviewers]
status: complete
last_updated: 2026-03-10
last_updated_by: OpenCode
specification_path: docs/spec/features/FEAT-183-remove-flat-spec-compatibility/
---

# Research: Implementation research for FEAT-183 remove flat-spec compatibility

## Research Question
Create a research document for implementing FEAT-183 using the CLI research-session guidance, with emphasis on all runtime, validation, prompt, documentation, fixture, and archived-spec surfaces that still support the old flat feature-spec layout. List the relevant functions/classes and describe how they support the legacy flat approach.

## Summary
- The current repository still supports two active feature entrypoint shapes: flat files under `docs/spec/features/*.yaml` and bundled package entrypoints under `docs/spec/features/<feature>/spec.yaml`. Discovery, validation, selection, archive/restore, progress tracking, prompts, reviewer guidance, and tests all still encode that dual-path model (`src/engineeringagent/spec_bundles.py:157`, `src/engineeringagent/specs.py:322`, `src/engineeringagent/loop_runtime/feature_state.py:94`, `src/engineeringagent/loop_runtime/selection.py:37`).
- Flat compatibility wrappers are still first-class in the codebase. The dedicated wrapper helpers resolve a flat wrapper to its canonical bundle and verify that wrapper `subtasks` mirror bundled `plan.md` phases (`src/engineeringagent/spec_bundles.py:172`, `src/engineeringagent/spec_bundles.py:182`, `src/engineeringagent/spec_bundles.py:250`).
- The approach CLI already exposes `research-session` and `plan-session`, but those topics are currently loaded from FEAT-181 supporting files in `docs/spec/features_done/.../supporting/` via repo-backed registry entries instead of packaged docs under `src/engineeringagent/approach/docs/` (`src/engineeringagent/approach/registry.py:33`, `src/engineeringagent/approach/registry.py:168`, `src/engineeringagent/cli/approach.py:43`).
- Reviewer prompts, contributor docs, and fitness/check surfaces still mention legacy wrappers or flat globs as valid workflow inputs (`harness/reviewers/prompts/intent_integrity_reviewer.md:13`, `harness/reviewers/prompts/test_reviewer.md:8`, `src/engineeringagent/approach/docs/workflow.md:17`, `src/engineeringagent/approach/docs/specifications.md:46`, `docs/references/documentation-practices.md:28`, `harness/checks.yaml:67`).
- Archived done specs are still mixed-format. The repository currently contains 179 flat files directly under `docs/spec/features_done/*.yaml`, and validation/discovery still treats those files as normal archived feature entrypoints (`src/engineeringagent/checks/validate/repo_validators.py:200`, `src/engineeringagent/loop_runtime/feature_state.py:176`). The requested cleanup direction is to remove all flat archived specs rather than preserve them through bundled replacements.

## Detailed Findings

### Feature discovery and schema dispatch
- `iter_feature_files()` returns both flat `*.yaml` files and bundled child `spec.yaml` files from one directory, then sorts them together. This is the common entrypoint for active and archived feature discovery (`src/engineeringagent/spec_bundles.py:157`).
- `FeatureSpec` is the schema for the legacy flat format and still includes `subtasks`, which is the legacy progress surface for flat active specs (`src/engineeringagent/specs.py:322`).
- `BundledFeatureSpec` is the schema for the bundled format and carries `planning_tier` plus `artifacts` instead of `subtasks` (`src/engineeringagent/specs.py:368`).
- `feature_contract_issues()` chooses between `FeatureSpec` and `BundledFeatureSpec` strictly from the file name. Any feature path whose name is not `spec.yaml` is still validated as a flat spec (`src/engineeringagent/specs.py:554`).
- `run_repo_validation()` applies `iter_feature_files()` to both `docs/spec/features` and `docs/spec/features_done`, so repository validation still treats flat active specs and flat archived specs as supported discovery units (`src/engineeringagent/checks/validate/repo_validators.py:186`).

### Explicit compatibility-wrapper support
- `resolve_compatibility_wrapper_canonical_spec_path()` maps a flat feature file like `docs/spec/features/FEAT-123.yaml` to `docs/spec/features/FEAT-123/spec.yaml`, which is the core helper for the old wrapper model (`src/engineeringagent/spec_bundles.py:172`).
- `_load_compatibility_wrapper_plan_phases()` loads wrapper `subtasks`, then loads the canonical bundled `spec.yaml` and its `plan.md` frontmatter so the two progress representations can be compared (`src/engineeringagent/spec_bundles.py:182`).
- `compatibility_wrapper_plan_mirror_issues()` reports drift between wrapper subtasks and bundled plan phases for count, title, status, and verification. This is direct enforcement of the wrapper-era mirror contract (`src/engineeringagent/spec_bundles.py:250`).
- `_matches_compatibility_wrapper_pair()` and `_compatibility_slug()` in the feature-id policy allow one flat active wrapper and one bundled active package to share the same base id when they describe the same feature slug (`src/engineeringagent/checks/validate/repo_policy_feature_ids.py:207`).
- Tests still assert this wrapper behavior directly, including wrapper-to-bundle resolution and wrapper/plan mirror enforcement (`tests/meta/test_spec_bundles.py:197`, `tests/meta/test_spec_bundles.py:226`, `tests/specs/test_specs_layout_smoke.py:85`).

### Runtime selection, progress, and archive behavior
- `resolve_feature_paths()` still accepts any explicit path ending in `.yaml` or `.yml`, loads it as YAML, and therefore continues to accept flat active spec paths as valid loop targets (`src/engineeringagent/loop_runtime/feature_state.py:94`).
- `discover_active_feature_paths()` uses `iter_feature_files()` over `docs/spec/features`, so run-all discovery still includes flat active specs if they exist (`src/engineeringagent/loop_runtime/feature_state.py:132`).
- `parse_selector_output()` indexes pending features by file name, feature id, and for bundled specs only by parent directory name. This keeps selector parsing compatible with both flat file names and bundled `spec.yaml` entrypoints (`src/engineeringagent/loop_runtime/selection.py:37`).
- `feature_storage_root()` and `resolve_feature_package_paths()` preserve both storage models: flat features move as single files, bundled features move as directories with `spec.yaml` (`src/engineeringagent/spec_bundles.py:278`, `src/engineeringagent/spec_bundles.py:286`).
- `archive_completed_feature()` and `restore_archived_feature()` rely on those dual-path helpers, so archive/restore still understands both flat and bundled feature storage (`src/engineeringagent/loop_runtime/feature_state.py:327`, `src/engineeringagent/loop_runtime/feature_state.py:366`).
- `feature_progress_kind()` still returns `subtask` for flat specs, `phase` for bundled specs with a plan, and `feature` for direct bundled specs. That keeps legacy flat subtask progress as a live runtime concept (`src/engineeringagent/spec_bundles.py:542`).
- `iter_progress_units()` falls back to `_iter_subtask_progress_units()` whenever the selected feature is not a bundled `spec.yaml` entrypoint with a usable plan, so flat features still produce subtask-shaped loop work units (`src/engineeringagent/loop_runtime/progress_units.py:102`).

### Prompt and reviewer surfaces
- `build_implementation_prompt()` derives prompt wording from `feature_progress_kind()`, so prompt behavior still changes based on whether the selected feature is flat or bundled (`src/engineeringagent/prompts/renderer.py:86`).
- `_progress_context_instruction()` tells the implementer to treat a flat feature as a temporary compatibility wrapper and follow the canonical bundled package references as the source of truth (`src/engineeringagent/prompts/renderer.py:140`).
- `_progress_update_instruction()` still instructs flat-feature runs to update the same feature YAML using subtask/feature status fields, which is legacy wrapper-era progress guidance (`src/engineeringagent/prompts/renderer.py:120`).
- `_progress_unit_prompt_label()` renders flat work as `compatibility-wrapper subtask`, keeping the old model visible in prompt text (`src/engineeringagent/prompts/renderer.py:154`).
- The reviewer prompts still scan both flat wrappers and bundled specs when `feature_path` is absent, and tell reviewers to follow a selected wrapper into its canonical bundled package (`harness/reviewers/prompts/intent_integrity_reviewer.md:11`, `harness/reviewers/prompts/test_reviewer.md:6`).
- The reviewer-authoring approach doc still teaches prompt authors to mention legacy wrappers explicitly when the active feature is a compatibility wrapper (`src/engineeringagent/approach/docs/reviewer-authoring.md:51`).

### Contributor docs, approach CLI, and the FEAT-181 session guides
- The workflow approach doc still describes a wrapper path in the core loop by naming a legacy compatibility wrapper and compatibility-wrapper verification commands (`src/engineeringagent/approach/docs/workflow.md:16`).
- The specifications approach doc is bundle-first, but it still documents flat wrappers as temporary migration shims (`src/engineeringagent/approach/docs/specifications.md:45`).
- `docs/references/documentation-practices.md` still says flat `docs/spec/features/*.yaml` files are temporary compatibility wrappers instead of removing them from the documented model (`docs/references/documentation-practices.md:25`).
- The approach topic order includes `research-session` and `plan-session`, but `_REPO_APPROACH_DOCS` sources those topics from `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/` instead of `src/engineeringagent/approach/docs/` (`src/engineeringagent/approach/registry.py:20`, `src/engineeringagent/approach/registry.py:33`).
- `_iter_repo_approach_topics()` reads those FEAT-owned markdown files directly from the repository tree, and `list_approach_topics()` merges them into the normal topic registry, which is why they already appear in `engineeringagent approach list` (`src/engineeringagent/approach/registry.py:168`, `src/engineeringagent/approach/registry.py:188`).
- `format_approach_topic_index()` renders the registry topic descriptions from frontmatter, so the FEAT-181 support docs behave like built-in approach topics in CLI output even though they are repo-backed (`src/engineeringagent/approach/rendering.py:8`).

### Checks, fitness rules, and smoke fixtures
- `harness/checks.yaml` still includes `docs/spec/features/*.yaml` in the `intent_integrity_reviewer` `on_change` globs, so checks configuration still treats flat active feature specs as a normal changed-file surface (`harness/checks.yaml:54`).
- `check_source_first_loop_commands.py` reimplements mixed-format feature discovery with both flat specs and bundled `spec.yaml` files, then scans flat `subtasks[*].verification` and bundled plan phases in one pass (`harness/fitness-functions/check_source_first_loop_commands.py:130`, `harness/fitness-functions/check_source_first_loop_commands.py:155`, `harness/fitness-functions/check_source_first_loop_commands.py:221`).
- That same fitness rule hard-codes the FEAT-181 `plan-session` and `research-session` files under `docs/spec/features_done/.../supporting/` as command-policy surfaces, so those repo-backed support docs are part of active verification today (`harness/fitness-functions/check_source_first_loop_commands.py:23`, `harness/fitness-functions/check_source_first_loop_commands.py:275`).
- The real OpenCode smoke fitness rule now writes a bundled active feature at `docs/spec/features/FEAT-001-hello-world-smoke/spec.yaml`, but `_parse_feature_statuses()` still falls back to legacy flat `subtasks` when no bundled plan phases are present (`harness/fitness-functions/check_real_opencode_hello_world_smoke.py:29`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:216`).

### Test coverage and repository fixtures
- `tests/meta/test_spec_bundles.py` contains direct legacy-wrapper helpers and fixtures, including `_write_flat_feature()` and tests for wrapper resolution and wrapper-plan mirror parity (`tests/meta/test_spec_bundles.py:13`, `tests/meta/test_spec_bundles.py:197`, `tests/meta/test_spec_bundles.py:226`).
- `tests/specs/test_specs_layout_smoke.py` still asserts that flat wrappers exist, point to canonical bundled specs, and mirror bundled plan phases (`tests/specs/test_specs_layout_smoke.py:85`).
- `tests/checks/reviewers/test_reviewer_prompt_bundled_guidance.py` and `tests/meta/test_spec_writing_reference_doc.py` assert the continued presence of `legacy wrappers (docs/spec/features/*.yaml)` language in prompts and docs (`tests/checks/reviewers/test_reviewer_prompt_bundled_guidance.py:6`, `tests/meta/test_spec_writing_reference_doc.py:283`).
- `tests/checks/reviewers/test_repo_reviewers_config.py` and `tests/checks/test_checks_reviewers_runtime.py` encode flat active-spec globs in expected reviewer config (`tests/checks/reviewers/test_repo_reviewers_config.py:31`, `tests/checks/test_checks_reviewers_runtime.py:129`).
- `tests/meta/test_validator.py` still covers flat active specs and flat archived done specs as valid validation surfaces, including a dedicated done-spec test that writes `docs/spec/features_done/FEAT-921-multiline-verification-done.yaml` (`tests/meta/test_validator.py:45`, `tests/meta/test_validator.py:134`).
- `tests/loop/test_loop_feature_iteration_prompt_guidance.py` still covers compatibility-wrapper prompt wording as an expected path, while bundled tests separately assert the bundled-only wording (`tests/loop/test_loop_feature_iteration_prompt_guidance.py:183`).

### Archived flat specs
- `run_repo_validation()` and `iter_feature_files()` still scan flat archived done specs directly from `docs/spec/features_done/*.yaml`, so archived flat files remain a supported repository state today (`src/engineeringagent/checks/validate/repo_validators.py:200`, `src/engineeringagent/spec_bundles.py:163`).
- The current repository contains 179 flat archived spec files directly under `docs/spec/features_done/`. FEAT-183 therefore covers not just code-path cleanup but also a large repository-content cleanup. User direction for this feature is to remove all flat archived specs rather than keep replacements as compatibility or retention artifacts.
- The active feature-id and archive-path logic still accepts mixed archived layout because bundled and flat done specs both flow through the same discovery and invariant checks (`src/engineeringagent/checks/validate/repo_policy_feature_ids.py:179`, `src/engineeringagent/checks/validate/repo_validators.py:318`).

## Code References
- `src/engineeringagent/spec_bundles.py:157` - mixed-format feature discovery for flat `*.yaml` and bundled `spec.yaml` entrypoints.
- `src/engineeringagent/spec_bundles.py:172` - flat-wrapper to canonical bundled-spec resolution.
- `src/engineeringagent/spec_bundles.py:182` - wrapper-subtask and bundled-plan loading for mirror validation.
- `src/engineeringagent/spec_bundles.py:250` - compatibility-wrapper mirror enforcement.
- `src/engineeringagent/spec_bundles.py:278` - flat-vs-bundled storage-root handling for archive/restore.
- `src/engineeringagent/spec_bundles.py:506` - bundled `plan.md` resolution from `spec.yaml` artifacts.
- `src/engineeringagent/spec_bundles.py:542` - runtime progress kind selection across subtask, phase, and feature models.
- `src/engineeringagent/specs.py:322` - legacy flat `FeatureSpec` model with `subtasks`.
- `src/engineeringagent/specs.py:368` - bundled `BundledFeatureSpec` model with `planning_tier` and `artifacts`.
- `src/engineeringagent/specs.py:554` - path-driven schema dispatch between flat and bundled contracts.
- `src/engineeringagent/loop_runtime/feature_state.py:94` - explicit feature-path acceptance for any YAML file.
- `src/engineeringagent/loop_runtime/feature_state.py:132` - run-all discovery through mixed-format feature iteration.
- `src/engineeringagent/loop_runtime/feature_state.py:327` - archive flow that still preserves flat-file archive semantics.
- `src/engineeringagent/loop_runtime/selection.py:37` - selector parsing for flat names, bundled parent names, and ids.
- `src/engineeringagent/loop_runtime/progress_units.py:102` - progress-unit iteration that falls back to subtasks for non-bundled cases.
- `src/engineeringagent/prompts/renderer.py:86` - implementation prompt rendering keyed by mixed progress kinds.
- `src/engineeringagent/approach/registry.py:20` - ordered approach topic ids, including `research-session` and `plan-session`.
- `src/engineeringagent/approach/registry.py:33` - repo-backed FEAT-181 support-doc registration for CLI approach topics.
- `src/engineeringagent/cli/approach.py:43` - CLI `approach list` rendering path.
- `harness/reviewers/prompts/intent_integrity_reviewer.md:11` - reviewer fallback scanning of flat wrappers and bundled specs.
- `harness/reviewers/prompts/test_reviewer.md:6` - same dual-format reviewer discovery path for test review.
- `harness/checks.yaml:54` - reviewer config still matching flat active-spec globs.
- `harness/fitness-functions/check_source_first_loop_commands.py:130` - mixed-format feature-spec scanning in fitness enforcement.
- `harness/fitness-functions/check_source_first_loop_commands.py:275` - FEAT-181 support docs treated as active approach-command surfaces.
- `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:216` - smoke rule status parsing that still supports legacy `subtasks` fallback.
- `tests/meta/test_spec_bundles.py:13` - flat feature fixture used to verify legacy behavior.
- `tests/specs/test_specs_layout_smoke.py:85` - smoke assertions that flat wrappers exist and map to bundled specs.
- `tests/checks/reviewers/test_repo_reviewers_config.py:31` - reviewer-config expectations that include flat feature globs.
- `tests/meta/test_validator.py:134` - archived flat done-spec validation scenario.

## Architecture Documentation
The current architecture is bundle-first in intent but still dual-path in operation. The shared entrypoint is path-based discovery: any feature directory may contribute flat YAML files and bundled `spec.yaml` files, and downstream behavior branches from the path shape rather than from a single canonical package abstraction (`src/engineeringagent/spec_bundles.py:157`, `src/engineeringagent/spec_bundles.py:315`). The flat model is carried by `FeatureSpec` plus `subtasks`; the bundled model is carried by `BundledFeatureSpec` plus `artifacts` and `plan.md` phases (`src/engineeringagent/specs.py:322`, `src/engineeringagent/specs.py:368`).

That duality propagates through runtime orchestration. Selection accepts any YAML path, run-all scans both layouts, progress tracking may be feature-, phase-, or subtask-shaped, and archive/restore still supports moving either a single flat file or a whole bundle directory (`src/engineeringagent/loop_runtime/feature_state.py:94`, `src/engineeringagent/loop_runtime/selection.py:69`, `src/engineeringagent/loop_runtime/progress_units.py:102`). Prompt text and reviewer instructions then expose the same model to agents by naming compatibility wrappers explicitly and instructing them to follow wrappers to canonical bundled packages (`src/engineeringagent/prompts/renderer.py:140`, `harness/reviewers/prompts/intent_integrity_reviewer.md:15`).

Approach guidance is also split between packaged docs and repo-backed FEAT-owned support docs. The CLI topic registry treats FEAT-181 support files as first-class approach topics even though they live under `docs/spec/features_done/.../supporting/`, not `src/engineeringagent/approach/docs/` (`src/engineeringagent/approach/registry.py:33`, `src/engineeringagent/approach/rendering.py:8`). This means FEAT-183 touches both feature-spec compatibility cleanup and approach-surface cleanup if the desired end state is for all approach docs to live under the packaged approach-doc tree.

## Open Questions
- None at this time.

