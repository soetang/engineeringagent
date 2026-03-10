---
plan_id: FEAT-181
feature_id: FEAT-181
status: done
source_spec: spec.yaml
source_research: research.md
planning_tier: researched
phases:
  - id: P1
    title: Redefine the bundled feature contract
    status: done
    verification:
      - uv run engineeringagent validate --schema-only
      - uv run pytest -q tests/meta/test_validator.py -k bundled_feature_contract
  - id: P2
    title: Add shared package discovery and bundled archive flow
    status: done
    verification:
      - uv run pytest -q tests/meta/test_coverage_threshold_regressions.py -k feature_state
      - uv run pytest -q tests/loop/test_loop_selection.py -k bundled
  - id: P3
    title: Move runtime sequencing and verification from subtasks to plan phases
    status: done
    verification:
      - uv run pytest -q tests/loop/test_loop_feature_iteration_verification.py -k phase
      - uv run pytest -q tests/loop/test_loop_feature_iteration_feedback.py -k phase
  - id: P4
    title: Remove unused CLI handoff/progress boundary
    status: done
    verification:
      - uv run pytest -q tests/cli/test_cli.py -k progress
      - uv run engineeringagent validate --schema-only
  - id: P5
    title: Remove non-essential summary/observer and helper cleanup drift
    status: done
    verification:
      - uv run pytest -q tests/loop/test_loop_output.py -k summary
      - uv run pytest -q tests/loop/test_loop_runtime_observers.py
      - uv run engineeringagent validate --schema-only
  - id: P6
    title: Add approach-list metadata and task-specific labels
    status: done
    verification:
      - uv run pytest -q tests/cli/test_cli.py -k approach_list
      - uv run pytest -q tests/cli/test_cli.py -k approach_show
  - id: P7
    title: Align docs, fitness rules, prompts, and smoke coverage
    status: done
    verification:
      - uv run pytest -q tests/fitness/test_fitness_rules_source_first_loop_commands.py
      - uv run pytest -q tests/harness/test_real_opencode_smoke.py
      - uv run pytest -q tests/meta/test_spec_writing_reference_doc.py
      - uv run pytest -q tests/specs/test_specs_layout_smoke.py
      - uv run pytest -q tests/cli/test_cli.py -k run_all
---

# FEAT-181 Plan

## Objective

- Deliver bundled feature packages for active and archived features while keeping `spec.yaml` as the canonical contract, preserving the current feature status vocabulary, and moving implementation sequencing from spec `subtasks` into `plan.md` phases.

## Architecture and Approach

- Introduce one shared feature-package abstraction that resolves a package root, canonical `spec.yaml`, declared artifacts, and archive destination; use it from runtime discovery, validation, and archive/restore flows instead of repeated flat-file `*.yaml` scans.
- Keep `spec.yaml` small and outcome-oriented by moving sequencing concerns out of the feature contract. The bundled spec should carry identity, status, acceptance, `planning_tier`, and deterministic artifact references, but not `subtasks`.
- Lock the initial planning-tier enum to three explicit values so authors and validators share one contract: `direct` (`spec.yaml` only), `planned` (`spec.yaml` + `plan.md`), and `researched` (`spec.yaml` + `research.md` + `plan.md`).
- Parse `plan.md` frontmatter with the existing markdown-plus-frontmatter pattern already used for approach docs, then validate it with a dedicated model so phases become the structured source for implementation sequencing and phase-scoped verification without taking over canonical feature status.
- Treat `plan.md` frontmatter as live execution metadata during implementation: the overall plan `status` and each phase `status` should be updated as work advances, while `spec.yaml` continues to own canonical feature lifecycle state.
- Archive done work by moving the whole feature package directory to `docs/spec/features_done/<feature-dir>/`, while continuing to treat `spec.yaml` as the runtime entrypoint path returned to selection, refresh, and validation code.
- Resolve the remaining FEAT-181 research decisions in the implementation contract: bundled folders apply to both active and done features, the feature-status vocabulary stays `backlog`/`in_progress`/`done`/`blocked`, and the migration includes the broader prompt/doc/test surfaces that still reference flat paths.
- Keep room for feature-local custom validation scripts under supporting artifacts when a spec needs a brittle or one-off proof step; document them as temporary, spec-scoped verification aids rather than default long-lived repository checks.
- Review affected fitness functions as a first-class planning surface; FEAT-181 changes enough long-lived workflow structure that the manifest, published fitness catalog, source-first loop rule, and real-agent smoke rule should all be evaluated for updates or quality improvements.
- Surface the research and planning approach files through the CLI approach registry so `uv run engineeringagent approach list` exposes them as first-class guidance topics rather than leaving them discoverable only by path, and drive the task-specific warning text from explicit frontmatter metadata instead of bloating titles.

```yaml
# target bundled spec shape
id: FEAT-181
planning_tier: researched
status: backlog
artifacts:
  plan: plan.md
  research: research.md
```

```python
class FeaturePackage(BaseModel):
    root: Path
    spec_path: Path
    planning_tier: PlanningTier
    artifacts: FeatureArtifacts


def iter_feature_packages(features_root: Path) -> list[FeaturePackage]:
    return [load_feature_package(path) for path in sorted(features_root.iterdir())]
```

```yaml
# target plan frontmatter shape
plan_id: FEAT-181
feature_id: FEAT-181
status: in_progress
planning_tier: researched
phases:
  - id: P2
    title: Add shared package discovery and bundled archive flow
    status: in_progress
```

## Interfaces and Impacted Surfaces

- `src/engineeringagent/specs.py:275` - current `SubtaskSpec` and `FeatureSpec` contract still model sequencing inside the feature spec and must be replaced with bundled-spec fields plus no `subtasks`.
- `src/engineeringagent/specs.py:289` - the canonical feature model needs an explicit `planning_tier` enum and artifact contract that names `direct`, `planned`, and `researched` with their required files.
- `src/engineeringagent/specs.py:440` - `iter_feature_files()` is the current flat scan helper and should become a package-aware discovery surface shared by runtime and validators.
- `src/engineeringagent/loop_runtime/feature_state.py:106` - active discovery scans `docs/spec/features/*.yaml`, while `src/engineeringagent/loop_runtime/feature_state.py:150` archives a single YAML file instead of a bundled feature directory.
- `src/engineeringagent/loop_runtime/selection.py:37` - selector parsing and deterministic fallback currently assume flat filenames and must continue to work with bundled `.../spec.yaml` entrypoints.
- `src/engineeringagent/loop_runtime/iteration.py:179` and `src/engineeringagent/loop_runtime/phases.py:282` - verification currently snapshots and executes newly-done `subtasks`, which must shift to plan-phase metadata.
- `src/engineeringagent/loop_runtime/feature_state.py:106`, `src/engineeringagent/loop_runtime/progress_units.py:1`, and `src/engineeringagent/loop_runtime/implement.py:1` - iteration-start sync, progress-unit selection, fallback context, and post-implement refresh must all resolve bundled work through plan phases rather than subtask-era assumptions.
- `src/engineeringagent/progress/handoff.py:15` and `src/engineeringagent/loop_runtime/telemetry.py:163` - runtime-written handoff entries and telemetry should preserve phase identity and wording without introducing a new manual CLI boundary.
- `src/engineeringagent/loop.py:1` and `src/engineeringagent/loop_runtime/observers.py:1` - loop summary/reporting should only change where required to surface existing runtime phase metadata, not to create separate CLI-only progress behavior.
- `src/engineeringagent/checks/validate/repo_validators.py:183` and `src/engineeringagent/checks/validate/repo_policy_feature_ids.py:26` - repo validation and feature-id invariants are still file-based and must validate packaged active/done specs plus companion artifacts.
- `src/engineeringagent/approach/registry.py:67` - existing markdown frontmatter parsing is the best implementation pattern for `plan.md` metadata loading.
- `src/engineeringagent/approach/registry.py:57`, `src/engineeringagent/approach/rendering.py:8`, and `src/engineeringagent/cli/approach.py:42` - the current CLI approach registry only exposes `approach_id` plus H1 title, so FEAT-181 needs frontmatter-backed description metadata and updated rendering for task-specific list labels.
- `src/engineeringagent/cli/progress.py:1` and `src/engineeringagent/cli/typer.py:1` - any manual handoff/progress append or prune CLI boundary not used by the loop should be removed rather than expanded.
- `docs/fitness-functions/rules.md:33` and `harness/fitness-functions/rules.yaml:1` - the fitness catalog and manifest need review because FEAT-181 changes long-lived workflow scope and rule wording.
- `harness/fitness-functions/check_source_first_loop_commands.py:17` - the source-first loop rule still scans flat specs and `subtasks[*].verification`, so it is a direct contract-update surface.
- `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:24` and `harness/fitness-functions/real_opencode_hello_world_feature_template.yaml:1` - the smoke rule and template currently encode flat paths and subtask-owned verification/status, so they should move with the bundled workflow.
- `src/engineeringagent/approach/docs/plan-session.md:1`, `src/engineeringagent/approach/docs/research-session.md:1`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/spec-format-example.yaml:1`, and `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-format-example.md:1` - the packaged session guidance and bundled examples are part of the workflow contract and should stay aligned with the implemented workflow.
- `README.md:19`, `src/engineeringagent/approach/docs/specifications.md:14`, `harness/reviewers/prompts/intent_integrity_reviewer.md:11`, `harness/fitness-functions/check_source_first_loop_commands.py:17`, and `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:24` still encode flat-file or subtask-era assumptions that must be updated.

## Refactoring Strategy

- First separate package discovery from feature-contract validation so bundled folders become one reusable abstraction instead of a series of local `glob("*.yaml")` exceptions.
- Remove subtask-specific model invariants and archive normalization before switching loop execution to phase metadata; that avoids carrying both sequencing systems long term.
- Keep `plan.md` parsing and artifact enforcement inside feature-package validation/runtime helpers instead of a generic markdown utility so ownership boundaries remain explicit.
- Change archive and restore helpers to move package directories while still returning canonical `spec.yaml` paths; this keeps the loop controller path-based without preserving flat-file storage.
- Continue treating fresh-session rules as documentation guidance only; validators should enforce package shape, artifact presence, and metadata correctness, but not session behavior.
- Make status synchronization part of the implementation shape: plan-writing and phase-advancement code should update `plan.md` frontmatter in place whenever a phase starts or completes, without mirroring those transitions back into a second feature-status system.
- For fitness functions, prefer improving long-lived rules when FEAT-181 exposes a cleaner durable boundary, but keep spec-local custom validation scripts separate as temporary supporting artifacts rather than folding them into the fitness catalog by default.

## Phase Plan

### Phase 1: Redefine the bundled feature contract
- Goal: make the bundled `spec.yaml` and `plan.md` contracts explicit, preserve the existing feature status vocabulary, and remove `subtasks` from active feature specs.
- Areas touched: `src/engineeringagent/specs.py`, feature schema generation, FEAT-181 contract examples, and any validator helpers that assume `subtasks` are present.
- Interfaces: `FeatureSpec`, the `direct`/`planned`/`researched` planning-tier enum, tier-specific `artifacts` requirements, plan-frontmatter phase schema, status vocabulary, rejection of legacy `subtasks` in active bundled specs, and the contract that research/planning approach docs are CLI-discoverable.
- Refactoring: remove subtask-specific invariants and isolate reusable package metadata types before touching runtime discovery.
- Verification:
  - `uv run engineeringagent validate --schema-only`
  - `uv run pytest -q tests/meta/test_validator.py -k bundled_feature_contract`
- Example verification design:

```python
def test_researched_tier_requires_plan_and_research_artifacts(tmp_path: Path) -> None:
    write_spec(tmp_path, planning_tier="researched", artifacts={"plan": "plan.md"})
    messages = validate(project_root=tmp_path)
    assert any("research.md" in message for message in messages)


def test_active_bundled_spec_rejects_subtasks(tmp_path: Path) -> None:
    write_spec(tmp_path, planning_tier="planned", subtasks=[{"id": "ST-001"}])
    messages = validate(project_root=tmp_path)
    assert any("subtasks" in message for message in messages)
```

- Documentation changes: update FEAT-181 contract text and examples so the target bundled spec shape is explicitly no-subtask and phase-driven.

### Phase 2: Add shared package discovery and bundled archive flow
- Goal: discover active and done features as bundled folders with canonical `spec.yaml` entrypoints and archive done work by package directory.
- Areas touched: `src/engineeringagent/specs.py`, `src/engineeringagent/loop_runtime/feature_state.py`, `src/engineeringagent/loop_runtime/selection.py`, `src/engineeringagent/checks/validate/repo_validators.py`, `src/engineeringagent/checks/validate/repo_policy_feature_ids.py`, and the fitness-rule surfaces that hard-code flat discovery assumptions.
- Interfaces: package discovery helper, selector path tokens, directory-name/id invariants, and archive destination resolution under `docs/spec/features_done/<feature-dir>/spec.yaml`.
- Refactoring: replace duplicated flat-file scans with one package-aware helper consumed by runtime discovery, repo validation, and archive/restore code.
- Verification:
  - `uv run pytest -q tests/meta/test_coverage_threshold_regressions.py -k feature_state`
  - `uv run pytest -q tests/loop/test_loop_selection.py -k bundled`
- Example verification design:

```python
def test_discover_active_feature_packages_returns_spec_entrypoints(tmp_path: Path) -> None:
    create_feature_package(tmp_path, "FEAT-100-example", status="backlog")
    paths = discover_active_feature_paths(tmp_path)
    assert paths == [tmp_path / "docs/spec/features/FEAT-100-example/spec.yaml"]


def test_archive_completed_feature_moves_package_directory(tmp_path: Path) -> None:
    feature_path = create_feature_package(tmp_path, "FEAT-100-example", status="done")
    ok, archived_path, message = archive_completed_feature(tmp_path, feature_path)
    assert (ok, message) == (True, "")
    assert archived_path == tmp_path / "docs/spec/features_done/FEAT-100-example/spec.yaml"
```

- Documentation changes: update path examples and any archived-feature references to describe bundled active and bundled done folders.

### Phase 3: Move runtime sequencing and verification from subtasks to plan phases
- Goal: run runtime-owned iteration sequencing, verification, retry feedback, and post-implement bookkeeping from `plan.md` phase metadata instead of spec `subtasks`.
- Areas touched: `src/engineeringagent/loop_runtime/iteration.py`, `src/engineeringagent/loop_runtime/phases.py`, `src/engineeringagent/loop_runtime/feature_state.py`, `src/engineeringagent/loop_runtime/progress_units.py`, `src/engineeringagent/loop_runtime/implement.py`, `src/engineeringagent/progress/handoff.py`, `src/engineeringagent/loop_runtime/telemetry.py`, and the loop-test fixtures that currently synthesize `subtasks`.
- Functions and classes that may change in this phase:
  - `src/engineeringagent/loop_runtime/iteration.py`: `IterationPipelineDependencies`, `_apply_initial_load_result()`, `_run_verification_phase_if_passed()`, `_refresh_feature_after_implement_if_ready()`, `_archive_selected_feature_if_needed()`, `_resolve_progress_feature_path()`, `run_feature_iteration_pipeline()`.
  - `src/engineeringagent/loop_runtime/feature_state.py`: `_touch_active_plan_for_iteration()`, `_sync_active_plan_after_implement()`, `_normalize_done_plan()`, `_normalize_done_progress_artifacts()`, `refresh_feature_after_implement()`, `touch_active_feature_for_iteration()`, `archive_completed_feature()`.
  - `src/engineeringagent/loop_runtime/progress_units.py`: `ProgressUnit`, `progress_status_snapshot()`, `done_transition_verification_commands()`, `current_progress_unit()`, `iter_progress_units()`, `_iter_plan_progress_units()`, `_iter_raw_plan_progress_units()`, `_iter_subtask_progress_units()`.
  - `src/engineeringagent/loop_runtime/implement.py`: `_fallback_progress_context()` and only the fallback/output plumbing needed for runtime-owned phase context.
  - `src/engineeringagent/progress/handoff.py`: `HandoffRenderMetadata`, `fallback_implement_progress_envelope()`, `_format_progress_reference()`, `render_handoff_markdown_entry()`, `_render_progress_context_line()`, `_render_progress_reference_label()`.
  - `src/engineeringagent/loop_runtime/telemetry.py`: `write_iteration_telemetry()` and `_append_feature_handoff_markdown()`.
- Functions and classes that should not change in this phase unless a concrete failing runtime test proves they are required:
  - `src/engineeringagent/cli/progress.py`: `cmd_progress_handoff_append()`, `cmd_progress_feature_prune()`, `_read_json_stdin_payload()`, `_require_feature_id()`.
  - `src/engineeringagent/cli/typer.py`: command registration for `progress handoff-append` / `progress feature-prune`.
  - `src/engineeringagent/loop.py`: `print_summary()`.
  - `src/engineeringagent/loop_runtime/observers.py`: `publish_iteration_report()`, `build_console_observer()`, `build_default_iteration_report_observers()`.
- Interfaces: phase status snapshots, phase-scoped verification commands, plan-frontmatter phase updates, live plan/phase status persistence, retry/fallback context, runtime-written handoff wording, and telemetry fields that expose the current runtime unit of work.
- Refactoring: replace subtask-diff helpers with plan-phase helpers while keeping feature-level status and acceptance in `spec.yaml` unchanged, and avoid broadening the public CLI surface while doing so.
- Explicitly out of scope: manual `engineeringagent progress` CLI affordances, CLI readers/writers for handoff artifacts, validator/discovery/schema work already covered by earlier phases, and summary/observer reshaping that is not required for runtime phase ownership.
- Done criteria: bundled planned/researched features run end-to-end without relying on spec `subtasks`, phase/frontmatter status remains synchronized across iteration touch, implement refresh, archive, and fallback paths, and the full `-k phase` verification/feedback pair passes before this phase is marked done.
- Verification:
  - `uv run pytest -q tests/loop/test_loop_feature_iteration_verification.py -k phase`
  - `uv run pytest -q tests/loop/test_loop_feature_iteration_feedback.py -k phase`
- Example verification design:

```python
def test_phase_completion_updates_plan_frontmatter(tmp_path: Path) -> None:
    feature_path = create_feature_package(tmp_path, "FEAT-100-example", planning_tier="planned")
    mark_phase_done(feature_path.parent / "plan.md", phase_id="P1")
    plan = load_plan_artifact(feature_path.parent / "plan.md")
    assert plan.phases[0].status == "done"


def test_newly_completed_phase_runs_plan_verification_commands(tmp_path: Path) -> None:
    feature_path = create_feature_package_with_plan_verification(tmp_path, command="uv run pytest -q tests/unit/test_example.py")
    outcome = run_phase_verification(tmp_path, feature_path)
    assert outcome.verification_status == "passed"
```

- Documentation changes: explain that implementation sequencing, phase status, and per-phase verification now live in `plan.md`, not `spec.yaml`, and note that handoff/progress artifacts remain runtime-owned rather than a user-facing CLI workflow.

### Phase 4: Remove unused CLI handoff/progress boundary
- Goal: remove any manual CLI entrypoints and related test/plumbing for handoff/progress artifacts that are not used by the loop runtime.
- Areas touched: `src/engineeringagent/cli/progress.py`, `src/engineeringagent/cli/typer.py`, and any tests or helper code added only to support manual progress append/prune paths.
- Functions and classes to remove or simplify in this phase:
  - `src/engineeringagent/cli/progress.py`: `cmd_progress_handoff_append()`, `cmd_progress_feature_prune()`, `_read_json_stdin_payload()`, `_require_feature_id()`.
  - `src/engineeringagent/cli/typer.py`: progress command wiring for `handoff-append` and `feature-prune`.
  - `tests/cli/test_cli.py`: `test_progress_handoff_append_reads_json_stdin_and_appends_markdown()`, `test_progress_handoff_append_uses_fallback_for_invalid_json()`, `test_progress_handoff_append_preserves_progress_metadata()`, and the `feature-prune` CLI coverage.
- Interfaces: CLI surface inventory, command registration, and any progress-render metadata plumbing that exists only for unused manual CLI paths.
- Refactoring: delete unused CLI compatibility paths instead of preserving or expanding them; keep runtime-written handoff artifact generation in the loop-owned code path.
- Verification:
  - `uv run pytest -q tests/cli/test_cli.py -k progress`
  - `uv run engineeringagent validate --schema-only`
- Documentation changes: none beyond keeping FEAT-181 scope notes explicit that handoff/progress artifacts are runtime internals.

### Phase 5: Remove non-essential summary/observer and helper cleanup drift
- Goal: remove or defer cleanup drift that is not required for phase-owned runtime behavior, especially console-summary/observer reshaping and helper-only refactors introduced during ST-003 work.
- Areas touched: `src/engineeringagent/loop.py`, `src/engineeringagent/loop_runtime/observers.py`, `tests/loop/test_loop_output.py`, `tests/loop/test_loop_runtime_observers.py`, `tests/loop/test_loop_contracts.py`, `tests/loop/feature_iteration_feedback_support.py`, `tests/loop/test_feature_iteration_feedback_support.py`, and `tests/meta/validator_support.py`.
- Functions and classes to review and either keep minimal or remove/defer:
  - `src/engineeringagent/loop.py`: `print_summary()`.
  - `src/engineeringagent/loop_runtime/observers.py`: `TelemetryObserverDependencies`, `ConsoleObserverDependencies`, `DefaultObserverDependencies`, `publish_iteration_report()`, `build_telemetry_observer()`, `build_console_observer()`, `build_default_iteration_report_observers()`.
  - `tests/loop/feature_iteration_feedback_support.py`: `install_stateful_prompt_agent()`, `advance_bundled_plan_prompt_state()`, `advance_subtask_prompt_state()`.
  - `tests/meta/validator_support.py`: `write_bundled_feature_spec()`, `write_plan_artifact()`, `write_legacy_feature_wrapper()` if they exist only to carry unrelated refactor churn rather than current behavior coverage.
- Tests that should be removed or deferred unless a concrete runtime requirement proves they are necessary:
  - `tests/loop/test_loop_output.py::test_non_verbose_terminal_output_surfaces_phase_progress_context`.
  - `tests/loop/test_loop_runtime_observers.py::test_console_observer_prints_summary_and_failed_log_pointer`.
  - `tests/loop/test_loop_runtime_observers.py::test_default_observers_publish_telemetry_before_console`.
  - `tests/loop/test_loop_contracts.py::test_print_summary_signature_is_explicit`.
- Tests that should stay because they cover runtime-owned telemetry/handoff behavior rather than optional console shaping:
  - `tests/loop/test_loop_output.py::test_handoff_markdown_entry_includes_phase_progress_context`.
  - `tests/loop/test_loop_output.py::test_write_iteration_telemetry_appends_handoff_entry_from_envelope`.
  - `tests/loop/test_loop_output.py::test_write_iteration_telemetry_uses_phase_wording_for_fallback_handoff`.
  - `tests/loop/test_loop_output.py::test_write_iteration_telemetry_uses_feature_wording_for_direct_bundle_fallback_handoff`.
  - `tests/loop/test_loop_runtime_observers.py::test_publish_iteration_report_applies_observers_in_order`.
  - `tests/loop/test_loop_runtime_observers.py::test_telemetry_observer_writes_telemetry_and_sets_log_path`.
- Interfaces: observer/reporting contracts should remain as small as possible; helper extraction should stay only where it reduces duplication for behavior still kept in-scope.
- Refactoring: prefer deletion/defer over keeping broad API reshaping; if a summary/observer change is necessary, tie it to one specific runtime phase-context requirement and corresponding failing test.
- Verification:
  - `uv run pytest -q tests/loop/test_loop_output.py -k summary`
  - `uv run pytest -q tests/loop/test_loop_runtime_observers.py`
  - `uv run engineeringagent validate --schema-only`
- Documentation changes: none; this is a scope-control cleanup phase.

### Phase 6: Add approach-list metadata and task-specific labels
- Goal: extend approach-topic metadata and rendering so `engineeringagent approach list` can show task-specific descriptions from frontmatter for research/planning topics without overloading titles, while `engineeringagent approach <topic>` renders the markdown body without frontmatter.
- Areas touched: `src/engineeringagent/approach/registry.py`, `src/engineeringagent/approach/rendering.py`, `src/engineeringagent/cli/approach.py`, packaged approach docs, and the bundled research/planning session guides.
- Interfaces: approach frontmatter schema, `ApproachTopic` metadata model, CLI list rendering format, CLI topic rendering without frontmatter, and the task-specific descriptions for research/planning topics.
- Refactoring: separate approach topic title rendering from list-description rendering so future topics can stay concise in `show` output while still carrying richer list metadata.
- Verification:
  - `uv run pytest -q tests/cli/test_cli.py -k approach_list`
  - `uv run pytest -q tests/cli/test_cli.py -k approach_show`
- Example verification design:

```python
def test_approach_list_uses_frontmatter_description_for_task_specific_topics() -> None:
    output = run_cli("approach", "list")
    assert "research-session" in output
    assert "only when creating research.md" in output
    assert "plan-session" in output
    assert "only when creating plan.md" in output


def test_approach_show_keeps_document_title_clean() -> None:
    output = run_cli("approach", "show", "plan-session")
    assert "# " in output
    assert "only when creating" not in first_heading(output)
    assert not output.lstrip().startswith("---")
```

- Documentation changes: explain that task-specific CLI approach labels come from frontmatter metadata, not from stuffing warnings into the visible title, and that `approach show` hides frontmatter from end users.

### Phase 7: Align docs, fitness rules, prompts, and smoke coverage
- Goal: remove flat-file and subtask-era guidance from repository docs, reviewer prompts, fitness rules, smoke rules, and examples so authored guidance matches the enforced workflow.
- Areas touched: `README.md`, `src/engineeringagent/approach/docs/specifications.md`, `src/engineeringagent/approach/registry.py`, `src/engineeringagent/cli/approach.py`, reviewer prompts, `docs/fitness-functions/rules.md`, `harness/fitness-functions/rules.yaml`, affected fitness scripts, smoke templates, metadata/layout tests, and FEAT-181 supporting examples.
- Interfaces: author-facing spec location guidance, reviewer fallback discovery, reviewer access to plan phases and planning tiers, smoke-template paths, verification-command scanning surfaces that still assume flat YAML specs, tier guidance that explains when to use `direct`, `planned`, or `researched`, documentation for spec-local custom validation scripts, fitness-rule scope/behavior for bundled feature packages, and CLI approach topic discovery for the research/planning session guides.
- Refactoring: consolidate repeated layout assumptions to shared package-entrypoint wording so docs and enforcement do not drift again.
- Verification:
  - `uv run pytest -q tests/fitness/test_fitness_rules_source_first_loop_commands.py`
  - `uv run pytest -q tests/harness/test_real_opencode_smoke.py`
  - `uv run pytest -q tests/meta/test_spec_writing_reference_doc.py`
  - `uv run pytest -q tests/specs/test_specs_layout_smoke.py`
  - `uv run pytest -q tests/cli/test_cli.py -k run_all`
- Example verification design:

```python
def test_source_first_rule_scans_plan_phase_verification(tmp_path: Path) -> None:
    write_plan_with_verification(tmp_path, command="uvx --from . engineeringagent validate")
    proc, payload = run_source_first_rule(tmp_path)
    assert proc.returncode == 1
    assert "plan.md:phases[0].verification[0]" in payload["violations"][0]


def test_real_smoke_template_uses_bundled_feature_package(repo_root: Path) -> None:
    payload = load_smoke_feature_template(repo_root)
    assert payload["artifacts"]["plan"] == "plan.md"
    assert payload["planning_tier"] in {"planned", "researched"}


def test_approach_list_includes_research_and_plan_session_topics() -> None:
    output = run_cli("approach", "list")
    assert "research-session" in output
    assert "plan-session" in output
    assert "only when creating research.md" in output
    assert "only when creating plan.md" in output
```

- Documentation changes: explain bundled active/done folders, spec-first then fresh-session research then fresh-session planning, the fact that plan phases now own implementation sequencing, how long-lived fitness rules differ from temporary spec-local custom validation files, and that the bundled session guides are available from `uv run engineeringagent approach list` with labels showing they are not general reading.

## Verification Strategy

- Start with schema and contract validation so bundled package discovery and plan parsing are built on stable models before runtime behavior changes.
- Add targeted validator and runtime regressions before broad doc updates; this keeps path migration and phase sequencing failures localized while the implementation shape settles.
- Run `uv run engineeringagent validate --schema-only` during contract work, then `uv run engineeringagent validate` once artifact presence and plan parsing are wired into repo validation.
- Use loop tests to cover both bundled-path behavior and phase-driven verification, especially selector fallback parsing, archive-after-done behavior, and progress output that currently references subtasks.
- Review impacted fitness rules before the final documentation pass; for FEAT-181 that includes the manifest/catalog surfaces plus the source-first loop rule and the real-agent smoke rule.
- Use targeted test designs that prove both structural behavior and policy alignment, for example:

```python
def test_discover_active_feature_packages_returns_spec_entrypoints(tmp_path: Path) -> None:
    create_feature_package(tmp_path, "FEAT-100-example", status="backlog")
    paths = discover_active_feature_paths(tmp_path)
    assert paths == [tmp_path / "docs/spec/features/FEAT-100-example/spec.yaml"]


def test_phase_completion_updates_plan_frontmatter(tmp_path: Path) -> None:
    feature_path = create_feature_package(tmp_path, "FEAT-100-example", planning_tier="planned")
    mark_phase_done(feature_path.parent / "plan.md", phase_id="P1")
    plan = load_plan_artifact(feature_path.parent / "plan.md")
    assert plan.phases[0].status == "done"
```

```python
def test_source_first_rule_scans_plan_phase_verification(tmp_path: Path) -> None:
    write_plan_with_verification(tmp_path, command="uvx --from . engineeringagent validate")
    proc, payload = run_source_first_rule(tmp_path)
    assert proc.returncode == 1
    assert "plan.md:phases[0].verification[0]" in payload["violations"][0]
```

- Finish with docs, fitness tests, meta tests, and smoke coverage so user-facing guidance, policy checks, and templates only move after the runtime and validator contract is already enforced.

## Documentation Changes

- Update `README.md` and `src/engineeringagent/approach/docs/specifications.md` to point authors at `docs/spec/features/<feature-dir>/spec.yaml` and to explain that bundled done features archive under `docs/spec/features_done/<feature-dir>/spec.yaml`.
- Add one canonical description of planning tiers and artifact requirements: `direct` for spec-only work, `planned` when a plan is required, and `researched` when both research and a plan are required before implementation.
- Update `harness/reviewers/prompts/intent_integrity_reviewer.md` and `harness/reviewers/prompts/test_reviewer.md` to reference bundled spec entrypoints, planning tiers, plan phases, supporting artifacts, and the reviewer expectations introduced by the new package layout.
- Refresh `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/spec-format-example.yaml` and `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-format-example.md` so the examples show no-subtask specs and phase-owned sequencing.
- Keep `src/engineeringagent/approach/docs/plan-session.md` and `src/engineeringagent/approach/docs/research-session.md` aligned with the implemented workflow, including the expectation that plans carry concise design/test snippets and link relevant support artifacts.
- Make the supporting research/planning guides discoverable through the CLI approach registry and document their topic ids so users can reach them from `uv run engineeringagent approach list`, while making their task-specific scope obvious in the list output itself.
- Document the new approach frontmatter description field and when to use it for task-specific list labels versus the H1 title.
- Document that approach frontmatter is authoring metadata for discovery/rendering and is not shown in normal `engineeringagent approach <topic>` output.
- Document that `plan.md` status and per-phase statuses are maintained during execution as live planning metadata, distinct from the canonical feature `status` in `spec.yaml`.
- Document the purpose of custom validation files in supporting artifacts: they are allowed for deterministic, spec-specific, sometimes brittle verification, but they should not be kept as permanent shared checks unless they prove reusable beyond the current feature.
- Update fitness-rule documentation and manifest descriptions when rule scope or rationale changes, and document the difference between long-lived fitness rules and temporary spec-local validation helpers.
- Update smoke and fitness guidance tied to feature-spec paths so `docs/spec/features/*.yaml` assumptions become package-entrypoint rules.
- Update metadata tests and other supporting repo checks alongside the core runtime/validator surfaces rather than leaving flat-path references behind as follow-up cleanup.
- Clarify that validators enforce artifact and metadata rules, while fresh-session recommendations remain approach guidance rather than runtime state.

## Risks and Notes

- Removing `subtasks` reaches deeper than discovery and schema updates: verification, telemetry, handoff text, and several loop-test fixtures currently use subtask snapshots, so this should be treated as a runtime refactor rather than a docs-only migration.
- Bundled done-archive support changes move semantics from file moves to directory moves; archive, restore, and post-implement fallback logic must still return concrete `spec.yaml` paths so loop orchestration stays predictable.
- This plan resolves the open questions recorded in `research.md`: keep `backlog`, `in_progress`, `done`, and `blocked`; archive done features as bundled folders; and migrate the surrounding docs, prompts, smoke rules, and metadata tests in the same feature rather than limiting changes to runtime and validators.
- This plan also names the initial planning-tier contract explicitly: `direct`, `planned`, and `researched`, with increasing artifact requirements and no hidden implied tiers.
- Supporting validation scripts are intentionally allowed to be more brittle and spec-specific than normal shared tests, but the workflow should document them as temporary verification tools so the repo does not accumulate permanent one-off checks by default.
- FEAT-181 should explicitly decide whether each impacted fitness rule is merely path-adjusted or meaningfully improved; the plan assumes those quality-improving rule updates are in scope when the bundled workflow reveals a better long-lived boundary.
- Exposing feature-bundled session guides through the CLI approach registry likely requires either repo-local approach discovery or a deliberate promotion path into packaged approach topics; implementation should choose one explicit mechanism rather than relying on undocumented path knowledge.
- Reviewer prompts are a first-order migration surface here, not just documentation polish, because reviewers need enough bundled-package context to evaluate changes against `spec.yaml`, `plan.md` phases, planning tiers, and supporting verification artifacts.
- Because FEAT-181 already includes starter docs and examples, implementation should update those artifacts in the same phase that changes the enforced contract to avoid teaching stale shapes.
