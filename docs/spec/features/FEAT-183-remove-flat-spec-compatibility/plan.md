---
plan_id: FEAT-183
feature_id: FEAT-183
status: in_progress
source_spec: spec.yaml
source_research: research.md
planning_tier: researched
phases:
  - id: P1
    title: Cut the repository over to bundled-only feature contracts
    status: in_progress
    verification:
      - uv run engineeringagent validate --schema-only
      - uv run pytest -q tests/meta/test_validator.py -k bundled_only
      - uv run pytest -q tests/meta/test_spec_bundles.py -k bundled_only
  - id: P2
    title: Remove runtime wrapper handling and bundled-path fallbacks
    status: backlog
    verification:
      - uv run pytest -q tests/loop/test_loop_selection.py -k bundled_only
      - uv run pytest -q tests/loop/test_loop_feature_iteration_prompt_guidance.py -k bundled_only
      - uv run pytest -q tests/loop/test_feature_archive_subtasks_done.py -k bundled_only
  - id: P3
    title: Package `research-session` and `plan-session` docs and rewrite bundled-only guidance
    status: backlog
    verification:
      - uv run pytest -q tests/cli/test_approach_registry.py
      - uv run pytest -q tests/checks/reviewers/test_reviewer_prompt_bundled_guidance.py
      - uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py
  - id: P4
    title: Delete flat archived specs and add repo-wide cutover checks
    status: backlog
    verification:
      - uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_flat_feature_specs.py
      - uv run pytest -q tests/fitness/test_fitness_rules_source_first_loop_commands.py
      - uv run pytest -q tests/harness/test_real_opencode_smoke.py
      - uv run engineeringagent checks run --phase feature_done
---

# FEAT-183 Plan

## Objective

- Remove the last flat-spec compatibility paths so active and archived features are discovered, validated, selected, archived, documented, and reviewed only through bundled package entrypoints at `docs/spec/features/<feature>/spec.yaml` and `docs/spec/features_done/<feature>/spec.yaml`.

## Architecture and Approach

- Treat bundled `spec.yaml` as the only feature contract. Delete `FeatureSpec`, `SubtaskSpec`, `resolve_compatibility_wrapper_canonical_spec_path()`, `_load_compatibility_wrapper_plan_phases()`, and `compatibility_wrapper_plan_mirror_issues()` instead of preserving them behind replacement abstractions.
- Collapse shared discovery onto one invariant: feature roots contribute a spec only when a child `spec.yaml` exists. Runtime, validators, checks, and fitness rules should all consume that same invariant.
- Keep progress semantics bundle-first as introduced by FEAT-181: only `phase` and `feature` remain valid progress kinds. `subtask` and `compatibility-wrapper` wording should disappear from runtime and prompts.
- Promote `research-session` and `plan-session` into packaged approach docs under `src/engineeringagent/approach/docs/` so `engineeringagent approach` no longer depends on feature-owned files under `docs/spec/features_done/**/supporting/`.
- Use feature-local supporting scripts for three concrete repository proofs during this cleanup: `check_no_flat_feature_specs.py` for active/done layout absence, `check_no_repo_approach_wrappers.py` for packaged-approach cutover, and `check_prompt_surfaces_are_bundled_only.py` for prompt/reviewer wording removal, instead of expanding long-lived shared unit suites for these repo-wide absence checks.

```python
def iter_feature_files(features_dir: Path) -> list[Path]:
    return sorted(
        child / "spec.yaml"
        for child in features_dir.iterdir()
        if child.is_dir() and (child / "spec.yaml").is_file()
    )
```

```python
def feature_progress_kind(spec_path: Path, feature: dict[str, Any] | None) -> str:
    if resolve_feature_plan_path(spec_path, feature) is not None:
        return "phase"
    return "feature"
```

## Interfaces and Impacted Surfaces

- `src/engineeringagent/specs.py:308` - `SubtaskSpec` becomes dead code once flat specs are unsupported and should be removed with the legacy invariants helpers that only exist for `subtasks`.
- `src/engineeringagent/specs.py:322` - `FeatureSpec` currently models flat `docs/spec/features/*.yaml`; `BundledFeatureSpec` at `src/engineeringagent/specs.py:368` should become the only feature contract surfaced through `FeatureSpecContract`, `feature_schema_from_model()`, and `feature_contract_issues()`.
- `src/engineeringagent/spec_bundles.py:157` - `iter_feature_files()` is the mixed-format discovery seam used by validators and runtime and must become bundled-only.
- `src/engineeringagent/spec_bundles.py:172`, `src/engineeringagent/spec_bundles.py:182`, `src/engineeringagent/spec_bundles.py:250` - `resolve_compatibility_wrapper_canonical_spec_path()`, `_load_compatibility_wrapper_plan_phases()`, and `compatibility_wrapper_plan_mirror_issues()` are explicit wrapper support and should be deleted.
- `src/engineeringagent/spec_bundles.py:278`, `src/engineeringagent/spec_bundles.py:286`, `src/engineeringagent/loop_runtime/feature_state.py:327`, `src/engineeringagent/loop_runtime/feature_state.py:366` - archive/restore helpers still preserve flat file moves and must always move bundled directories.
- `src/engineeringagent/loop_runtime/feature_state.py:94`, `src/engineeringagent/loop_runtime/feature_state.py:132`, `src/engineeringagent/loop_runtime/selection.py:37` - explicit feature-path resolution, run-all discovery, and selector token parsing still accept flat YAML paths and filenames.
- `src/engineeringagent/spec_bundles.py:542`, `src/engineeringagent/loop_runtime/progress_units.py:102`, `src/engineeringagent/prompts/renderer.py:86` - progress-unit selection and prompt rendering still branch on flat `subtask` / wrapper behavior.
- `src/engineeringagent/checks/validate/repo_validators.py:186`, `src/engineeringagent/checks/validate/repo_validators.py:252`, `src/engineeringagent/checks/validate/repo_policy_feature_ids.py:207` - repo validation still scans flat active/done specs, validates flat verification payloads, and allows wrapper/spec id pairs.
- `src/engineeringagent/approach/registry.py:33`, `src/engineeringagent/approach/registry.py:168` - `_REPO_APPROACH_DOCS` and `_iter_repo_approach_topics()` keep FEAT-owned session docs alive as first-class topics.
- `harness/reviewers/prompts/intent_integrity_reviewer.md:11`, `harness/reviewers/prompts/test_reviewer.md:6`, `harness/checks.yaml:54`, `harness/fitness-functions/check_source_first_loop_commands.py:130`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:216` - these files still mention or implement flat-spec behavior: reviewer fallback scans `docs/spec/features/*.yaml`, reviewer `on_change` still matches flat feature paths, the source-first fitness rule still scans flat feature specs and `subtasks[*].verification`, and the hello-world smoke rule still falls back to `subtasks` status parsing.

## Refactoring Strategy

- Start at the contract boundary: remove `FeatureSpec`, `SubtaskSpec`, `FeatureSpecContract` union support for flat specs, and mixed-format `iter_feature_files()` discovery before changing `resolve_feature_paths()`, `parse_selector_output()`, and prompt rendering, so stale flat-path behavior fails in validator/spec-bundle tests first.
- Centralize the bundled-only path rule in `iter_feature_files()`, `feature_storage_root()`, `resolve_feature_package_paths()`, and `feature_progress_kind()` before updating `src/engineeringagent/prompts/renderer.py`, `harness/reviewers/prompts/intent_integrity_reviewer.md`, `harness/reviewers/prompts/test_reviewer.md`, `harness/fitness-functions/check_source_first_loop_commands.py`, and `harness/fitness-functions/check_real_opencode_hello_world_smoke.py`; this removes repeated flat-path branching.
- Keep these repo-wide absence and wording checks in feature-local supporting scripts proposed for this feature:
  - `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_flat_feature_specs.py`
  - `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py`
- Prefer replacing wrapper-era assertions in `tests/meta/test_spec_bundles.py`, `tests/meta/test_validator.py`, `tests/specs/test_specs_layout_smoke.py`, `tests/loop/test_loop_selection.py`, and `tests/loop/test_feature_archive_subtasks_done.py` with bundled-only behavior checks, instead of adding more shared tests that only scan for deleted strings.
- Delete archived flat done specs in the same implementation window that removes validator/runtime support so the repo never sits in a mixed state after FEAT-183 is complete.

## Phase Plan

### Phase 1: Cut the repository over to bundled-only feature contracts

- Goal: make `src/engineeringagent/specs.py`, `src/engineeringagent/spec_bundles.py`, and `src/engineeringagent/checks/validate/repo_validators.py` accept only `docs/spec/features/<feature>/spec.yaml` and `docs/spec/features_done/<feature>/spec.yaml`.
- Areas touched: `src/engineeringagent/specs.py`, `src/engineeringagent/spec_bundles.py`, `src/engineeringagent/checks/validate/repo_validators.py`, `src/engineeringagent/checks/validate/repo_policy_feature_ids.py`, `tests/meta/test_validator.py`, `tests/meta/test_spec_bundles.py`, and `tests/specs/test_specs_layout_smoke.py`.
- Interfaces:
  - Remove `SubtaskSpec`, `FeatureSpec`, `_collect_subtask_state()`, and `_feature_status_alignment_errors()` from `src/engineeringagent/specs.py`.
  - Make `FeatureSpecContract` resolve only `BundledFeatureSpec`, update `feature_schema_from_model()`, and make `feature_contract_issues()` reject non-`spec.yaml` feature paths.
  - Simplify `iter_feature_files()` to enumerate only bundled entrypoints and delete wrapper helpers from `src/engineeringagent/spec_bundles.py`.
  - Remove `_matches_compatibility_wrapper_pair()` / `_compatibility_slug()` exceptions from `src/engineeringagent/checks/validate/repo_policy_feature_ids.py` so each feature id maps to one entrypoint.
  - Update `run_repo_validation()` and multiline verification checks in `src/engineeringagent/checks/validate/repo_validators.py` to inspect bundled active/done packages only.
- Refactoring: remove `SubtaskSpec`, `FeatureSpec`, `_collect_subtask_state()`, `_feature_status_alignment_errors()`, `resolve_compatibility_wrapper_canonical_spec_path()`, `_load_compatibility_wrapper_plan_phases()`, `compatibility_wrapper_plan_mirror_issues()`, and the wrapper-pair exceptions in `src/engineeringagent/checks/validate/repo_policy_feature_ids.py` before touching runtime selection and prompts, so contract validation has one bundled-only path.
- Verification:
  - `uv run engineeringagent validate --schema-only`
  - `uv run pytest -q tests/meta/test_validator.py -k bundled_only`
  - `uv run pytest -q tests/meta/test_spec_bundles.py -k bundled_only`
  - `uv run pytest -q tests/specs/test_specs_layout_smoke.py`
- Example verification design:

```python
def test_feature_contract_issues_rejects_flat_feature_path(tmp_path: Path) -> None:
    path = tmp_path / "docs/spec/features/FEAT-900-flat.yaml"
    write_yaml(path, valid_bundled_payload())
    issues = feature_contract_issues(load_yaml(path), path)
    assert any("spec.yaml" in issue.message for issue in issues)


def test_iter_feature_files_returns_only_bundled_specs(tmp_path: Path) -> None:
    create_feature_package(tmp_path, "FEAT-901-bundled")
    write_yaml(tmp_path / "docs/spec/features/FEAT-901-flat.yaml", {"id": "FEAT-901"})
    assert iter_feature_files(tmp_path / "docs/spec/features") == [
        tmp_path / "docs/spec/features/FEAT-901-bundled/spec.yaml"
    ]
```

- Documentation changes: update bundled-contract examples in `tests/meta/test_validator.py`, `tests/meta/test_spec_bundles.py`, and `tests/specs/test_specs_layout_smoke.py` so their fixture payloads and expected messages show only `docs/spec/features/<feature>/spec.yaml`, `docs/spec/features_done/<feature>/spec.yaml`, and plan phases, with no `subtasks` or wrapper-mirror expectations.

### Phase 2: Remove runtime wrapper handling and bundled-path fallbacks

- Goal: make `resolve_feature_paths()`, `discover_active_feature_paths()`, `parse_selector_output()`, `archive_completed_feature()`, `restore_archived_feature()`, `iter_progress_units()`, and prompt rendering in `src/engineeringagent/prompts/renderer.py` operate only on bundled entrypoints.
- Areas touched: `src/engineeringagent/loop_runtime/feature_state.py`, `src/engineeringagent/loop_runtime/selection.py`, `src/engineeringagent/spec_bundles.py`, `src/engineeringagent/loop_runtime/progress_units.py`, `src/engineeringagent/prompts/renderer.py`, `tests/loop/test_loop_selection.py`, `tests/loop/test_loop_feature_iteration_prompt_guidance.py`, `tests/loop/test_feature_archive_subtasks_done.py`, `tests/loop/test_selected_feature_load_without_archive_fallback.py`.
- Interfaces:
  - Restrict `resolve_feature_paths()` in `src/engineeringagent/loop_runtime/feature_state.py` to explicit bundled `spec.yaml` paths.
  - Keep `discover_active_feature_paths()`, `_discover_done_feature_paths()`, `archive_completed_feature()`, and `restore_archived_feature()` bundled-only.
  - Remove flat filename token support from `parse_selector_output()` and `_resolve_selector_candidates()` in `src/engineeringagent/loop_runtime/selection.py`; keep feature id and bundle directory name matching.
  - Simplify `feature_storage_root()`, `resolve_feature_package_paths()`, and `feature_progress_kind()` in `src/engineeringagent/spec_bundles.py`.
  - Delete `_iter_subtask_progress_units()` and the fallback branch in `iter_progress_units()` within `src/engineeringagent/loop_runtime/progress_units.py`.
  - Remove compatibility-wrapper wording from `build_implementation_prompt()`, `_progress_update_instruction()`, `_progress_context_instruction()`, and `_progress_unit_prompt_label()` in `src/engineeringagent/prompts/renderer.py`.
- Refactoring: after `resolve_feature_paths()`, `discover_active_feature_paths()`, `parse_selector_output()`, `feature_storage_root()`, and `resolve_feature_package_paths()` are bundled-only, remove `_iter_subtask_progress_units()` and the non-bundled fallback from `iter_progress_units()`, then simplify `feature_progress_kind()`, `build_implementation_prompt()`, `_progress_update_instruction()`, `_progress_context_instruction()`, and `_progress_unit_prompt_label()` so they handle only bundled phase work and direct bundled feature work.
- Verification:
  - `uv run pytest -q tests/loop/test_loop_selection.py -k bundled_only`
  - `uv run pytest -q tests/loop/test_loop_feature_iteration_prompt_guidance.py -k bundled_only`
  - `uv run pytest -q tests/loop/test_feature_archive_subtasks_done.py -k bundled_only`
  - `uv run pytest -q tests/loop/test_selected_feature_load_without_archive_fallback.py`
  - `uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_prompt_surfaces_are_bundled_only.py`
- Example verification design:

```python
def test_resolve_feature_paths_rejects_flat_yaml_target(tmp_path: Path) -> None:
    flat_path = tmp_path / "docs/spec/features/FEAT-910-flat.yaml"
    write_yaml(flat_path, {"id": "FEAT-910"})
    with pytest.raises(ValueError, match="bundled spec.yaml"):
        resolve_feature_paths(project_root=tmp_path, feature_paths=[flat_path])
```

- Documentation changes:
  - Update compatibility-wrapper wording in `src/engineeringagent/prompts/renderer.py`, specifically the strings emitted by `_progress_update_instruction()`, `_progress_context_instruction()`, and `_progress_unit_prompt_label()`, so they no longer mention `compatibility wrapper`, `canonical bundled package`, or `subtask` progress for active features.
  - Update `harness/reviewers/prompts/intent_integrity_reviewer.md` and `harness/reviewers/prompts/test_reviewer.md` so reviewer fallback instructions reference bundled `docs/spec/features/<feature>/spec.yaml` discovery only and no longer tell reviewers to follow a flat wrapper into another package.
  - Keep exact wording absence checks in `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_prompt_surfaces_are_bundled_only.py` rather than a permanent unit test.

### Phase 3: Package `research-session` and `plan-session` docs and rewrite bundled-only guidance

- Goal: move `research-session` and `plan-session` into `src/engineeringagent/approach/docs/`, remove `_REPO_APPROACH_DOCS` / `_iter_repo_approach_topics()` from `src/engineeringagent/approach/registry.py`, and rewrite the specific docs/prompts that still mention flat wrappers or FEAT-181 support-file sources.
- Areas touched: `src/engineeringagent/approach/registry.py`, `src/engineeringagent/approach/docs/workflow.md`, `src/engineeringagent/approach/docs/specifications.md`, `src/engineeringagent/approach/docs/reviewer-authoring.md`, new packaged docs `src/engineeringagent/approach/docs/research-session.md` and `src/engineeringagent/approach/docs/plan-session.md`, `docs/references/documentation-practices.md`, `harness/reviewers/prompts/intent_integrity_reviewer.md`, `harness/reviewers/prompts/test_reviewer.md`, `tests/cli/test_approach_registry.py`, `tests/cli/test_cli.py`, `tests/checks/reviewers/test_reviewer_prompt_bundled_guidance.py`, `tests/meta/test_spec_writing_reference_doc.py`.
- Interfaces:
  - Remove `_REPO_APPROACH_DOCS` and `_iter_repo_approach_topics()` from `src/engineeringagent/approach/registry.py` so `list_approach_topics()` is package-backed only.
  - Preserve existing topic ids `research-session` and `plan-session`, but source them from packaged markdown files under `src/engineeringagent/approach/docs/`.
  - Update `harness/reviewers/prompts/intent_integrity_reviewer.md` and `harness/reviewers/prompts/test_reviewer.md` so fallback discovery scans bundled `docs/spec/features/<feature>/spec.yaml` entrypoints only and never instructs reviewers to follow `docs/spec/features/*.yaml` wrappers.
  - Rewrite `src/engineeringagent/approach/docs/workflow.md`, `src/engineeringagent/approach/docs/specifications.md`, and `docs/references/documentation-practices.md` so `docs/spec/features/*.yaml` and FEAT-owned support-file approach docs are no longer described as valid repository shapes.
- Refactoring: move the session docs with minimal wording drift first, then simplify the registry so tests can lock a single approach-doc source model.
- Verification:
  - `uv run pytest -q tests/cli/test_approach_registry.py`
  - `uv run pytest -q tests/cli/test_cli.py -k approach`
  - `uv run pytest -q tests/checks/reviewers/test_reviewer_prompt_bundled_guidance.py`
  - `uv run pytest -q tests/meta/test_spec_writing_reference_doc.py`
  - `uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py`
- Example verification design:

```python
def test_research_session_topic_is_packaged() -> None:
    topic = next(t for t in list_approach_topics() if t.canonical_id == "research-session")
    assert topic.source == "package"
    assert topic.path.endswith("src/engineeringagent/approach/docs/research-session.md")


def test_intent_reviewer_prompt_mentions_only_bundled_specs() -> None:
    prompt = load_prompt("intent_integrity_reviewer.md")
    assert "docs/spec/features/*.yaml" not in prompt
    assert "compatibility wrapper" not in prompt
```

- Documentation changes:
  - Add `src/engineeringagent/approach/docs/research-session.md` and `src/engineeringagent/approach/docs/plan-session.md`.
  - Update `src/engineeringagent/approach/docs/workflow.md` to remove wrapper-path loop examples and bundled-wrapper verification wording.
  - Update `src/engineeringagent/approach/docs/specifications.md` to remove `docs/spec/features/*.yaml`, `legacy wrappers`, and any statement that flat files remain valid migration shims.
  - Update `src/engineeringagent/approach/docs/reviewer-authoring.md` so reviewer authors are told to reference bundled `spec.yaml`, `plan.md`, and supporting artifacts only.
  - Update `docs/references/documentation-practices.md` so feature layout examples show bundled active/done packages only.
  - Update `harness/reviewers/prompts/intent_integrity_reviewer.md` and `harness/reviewers/prompts/test_reviewer.md` so the fallback-selection instructions mention bundled `spec.yaml` entrypoints only.

### Phase 4: Delete flat archived specs and add repo-wide cutover checks

- Goal: delete every `docs/spec/features_done/*.yaml` file, remove flat-path handling from `harness/checks.yaml`, `harness/fitness-functions/check_source_first_loop_commands.py`, and `harness/fitness-functions/check_real_opencode_hello_world_smoke.py`, and add feature-local scripts that fail if those paths or phrases reappear.
- Areas touched: every flat archived file matching `docs/spec/features_done/*.yaml`, `harness/checks.yaml`, `harness/fitness-functions/check_source_first_loop_commands.py`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py`, `tests/fitness/test_fitness_rules_source_first_loop_commands.py`, `tests/harness/test_real_opencode_smoke.py`, `tests/checks/reviewers/test_repo_reviewers_config.py`, `tests/checks/test_checks_reviewers_runtime.py`, and the three supporting scripts under `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/`.
- Interfaces:
  - Delete remaining `docs/spec/features_done/*.yaml` files; if a done feature must stay present, keep it only as `docs/spec/features_done/<feature>/spec.yaml`.
  - Remove flat active-spec globs from `harness/checks.yaml` reviewer `on_change` surfaces.
  - Update `check_source_first_loop_commands.py` to scan bundled `spec.yaml` and bundled `plan.md` verification entries only, and point its approach-doc policy checks at packaged docs under `src/engineeringagent/approach/docs/`.
  - Update `_parse_feature_statuses()` in `harness/fitness-functions/check_real_opencode_hello_world_smoke.py` to stop falling back to flat `subtasks`.
  - Add migration-proof scripts:
    - `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_flat_feature_specs.py` to fail if active or done trees contain flat YAML feature entrypoints or if key docs/prompts still reference `docs/spec/features/*.yaml`.
    - `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py` to fail if `research-session` / `plan-session` still resolve from `docs/spec/features_done/**/supporting/`.
    - `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_prompt_surfaces_are_bundled_only.py` to scan generated prompt/reviewer guidance for retired wrapper/subtask-era phrases without freezing exact wording in a shared unit test.
- Refactoring: keep repo-wide absence assertions in `check_no_flat_feature_specs.py`, `check_no_repo_approach_wrappers.py`, and `check_prompt_surfaces_are_bundled_only.py`, while shared tests stay focused on durable behavior in `harness/checks.yaml`, `check_source_first_loop_commands.py`, `check_real_opencode_hello_world_smoke.py`, and their existing pytest coverage.
- Verification:
  - `uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_flat_feature_specs.py`
  - `uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py`
  - `uv run pytest -q tests/fitness/test_fitness_rules_source_first_loop_commands.py`
  - `uv run pytest -q tests/harness/test_real_opencode_smoke.py`
  - `uv run pytest -q tests/checks/reviewers/test_repo_reviewers_config.py`
  - `uv run pytest -q tests/checks/test_checks_reviewers_runtime.py`
  - `uv run engineeringagent checks run --phase feature_done`
- Example verification design:

```python
def main() -> int:
    flat_specs = sorted(ROOT.glob("docs/spec/features/*.yaml"))
    flat_done_specs = sorted(ROOT.glob("docs/spec/features_done/*.yaml"))
    forbidden_refs = search_forbidden_refs(patterns=[r"docs/spec/features/\*\.yaml"])
    if flat_specs or flat_done_specs or forbidden_refs:
        report(flat_specs, flat_done_specs, forbidden_refs)
        return 1
    return 0
```

- Documentation changes: no additional author docs in this phase; only keep the FEAT-183 supporting-script references in `docs/spec/features/FEAT-183-remove-flat-spec-compatibility/plan.md` aligned with the implemented script names.

## Verification Strategy

- First lock bundled-only schema/discovery in `src/engineeringagent/specs.py`, `src/engineeringagent/spec_bundles.py`, and `src/engineeringagent/checks/validate/repo_validators.py` with `tests/meta/test_validator.py`, `tests/meta/test_spec_bundles.py`, and `tests/specs/test_specs_layout_smoke.py` before changing loop code.
- Then run `tests/loop/test_loop_selection.py`, `tests/loop/test_loop_feature_iteration_prompt_guidance.py`, `tests/loop/test_feature_archive_subtasks_done.py`, and `tests/loop/test_selected_feature_load_without_archive_fallback.py` so runtime no longer accepts flat inputs even if stale files are reintroduced locally.
- After runtime is stable, update `src/engineeringagent/approach/registry.py`, `src/engineeringagent/approach/docs/workflow.md`, `src/engineeringagent/approach/docs/specifications.md`, `src/engineeringagent/approach/docs/reviewer-authoring.md`, `docs/references/documentation-practices.md`, `harness/reviewers/prompts/intent_integrity_reviewer.md`, and `harness/reviewers/prompts/test_reviewer.md`, then prove `research-session` and `plan-session` are package-backed only.
- Finish with the three FEAT-183 supporting scripts plus `tests/fitness/test_fitness_rules_source_first_loop_commands.py`, `tests/harness/test_real_opencode_smoke.py`, `tests/checks/reviewers/test_repo_reviewers_config.py`, and `tests/checks/test_checks_reviewers_runtime.py` so repo-wide absence checks remain feature-scoped while durable behavior stays covered by shared tests.

```python
def test_archive_completed_feature_returns_bundled_done_entrypoint(tmp_path: Path) -> None:
    feature_path = create_feature_package(tmp_path, "FEAT-920-example", status="done")
    ok, archived_path, message = archive_completed_feature(tmp_path, feature_path)
    assert (ok, message) == (True, "")
    assert archived_path == tmp_path / "docs/spec/features_done/FEAT-920-example/spec.yaml"
```

```bash
uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_flat_feature_specs.py
uv run python docs/spec/features/FEAT-183-remove-flat-spec-compatibility/supporting/check_no_repo_approach_wrappers.py
```

## Documentation Changes

- Add packaged `src/engineeringagent/approach/docs/research-session.md` and `src/engineeringagent/approach/docs/plan-session.md` with the current CLI guidance, then retire the FEAT-181 supporting copies from the active approach registry.
- Update `src/engineeringagent/approach/docs/workflow.md` to remove wrapper-path loop examples, `src/engineeringagent/approach/docs/specifications.md` to remove `docs/spec/features/*.yaml` / `legacy wrappers`, and `src/engineeringagent/approach/docs/reviewer-authoring.md` to require bundled `spec.yaml`, `plan.md`, and supporting-artifact references.
- Update `docs/references/documentation-practices.md` to document bundled active/done layout only.
- Update reviewer prompts and reviewer config docs so they reference bundled spec discovery, bundled plans, and supporting artifacts without mentioning flat wrappers.
- Keep `check_no_flat_feature_specs.py`, `check_no_repo_approach_wrappers.py`, and `check_prompt_surfaces_are_bundled_only.py` documented as temporary FEAT-183 migration checks so they can be deleted after bundled-only layout and prompt wording are stable.

## Risks and Notes

- Deleting `docs/spec/features_done/*.yaml` is large repository churn; use `check_no_flat_feature_specs.py` so reviewers can distinguish intentional archive deletion from missed files.
- Flat compatibility currently spans `src/engineeringagent/specs.py`, `src/engineeringagent/spec_bundles.py`, `src/engineeringagent/loop_runtime/feature_state.py`, `src/engineeringagent/prompts/renderer.py`, `src/engineeringagent/approach/registry.py`, `harness/checks.yaml`, `harness/fitness-functions/check_source_first_loop_commands.py`, and `harness/fitness-functions/check_real_opencode_hello_world_smoke.py`; landing only one subset will leave contradictory behavior behind.
- `check_no_flat_feature_specs.py`, `check_no_repo_approach_wrappers.py`, and `check_prompt_surfaces_are_bundled_only.py` are intentionally brittle because they assert repository absence conditions and exact retired phrases; keep them feature-local unless another feature reuses them.
- Rename or replace tests such as `tests/loop/test_feature_archive_subtasks_done.py` and wrapper-focused cases in `tests/meta/test_spec_bundles.py` so test names still describe the bundled-only behavior after the old code is gone.
