---
date: 2026-03-10T10:43:55+00:00
researcher: OpenCode
git_commit: e60898d
branch: master
repository: engineeringagent
topic: "Research for FEAT-184 delete legacy and low-value brittle tests"
tags: [research, codebase, tests, meta, fitness, loop]
status: complete
last_updated: 2026-03-10
last_updated_by: OpenCode
specification_path: docs/spec/features/FEAT-184-delete-low-value-tests/
---

# Research: Research for FEAT-184 delete legacy and low-value brittle tests

## Research Question
Create `research.md` for `docs/spec/features/FEAT-184-delete-low-value-tests/spec.yaml`, using the CLI research-session guidance, after thorough inspection of the test suite to identify legacy, brittle, low-value, heavily mocked, and implementation-coupled tests that are good deletion candidates while preserving behavior-facing anchors.

## Summary
- The main concentration of low-value tests is in `tests/meta` and `tests/fitness`, not the behavior-facing CLI, git, backend, or full loop-flow suites. Those two areas contain many repo-shape checks, migration guards, wording locks, deleted-path assertions, and checker self-tests that mostly enforce internal structure instead of user-visible behavior.
- The coverage and verification contract is explicit and must stay unchanged during cleanup: `pyproject.toml:26-27` keeps `--cov=engineeringagent --cov-fail-under=95 -n 2`, `tests/meta/test_validator.py:1781-1790` locks that declaration, and `harness/checks.yaml:30-34` keeps the repository on a full `uv run pytest -q` validation path.
- High-confidence whole-file deletion candidates are the legacy-shim and migration-guard files, wording-sync and repo-scan files, and several fitness-rule self-tests that only prove removed files stay removed or that repository layout remains encoded exactly (`tests/meta/test_legacy_shim_imports.py:9-39`, `tests/meta/test_no_gate_profile_references.py:18-63`, `tests/meta/test_legacy_checks_import_guard.py:15-109`, `tests/fitness/test_fitness_rules_repo_validators_boundary.py:6-28`, `tests/fitness/test_fitness_rules_test_layout_module_mirroring.py:56-110`, `tests/fitness/test_fitness_rules_no_doc_content_tests.py:40-164`).
- `tests/meta/test_spec_writing_reference_doc.py` is the clearest brittle wording-lock file. Its lower half asserts exact phrases across approach docs, templates, and examples, while only the early verification-command helper coverage is behavior-adjacent (`tests/meta/test_spec_writing_reference_doc.py:71-127`, `tests/meta/test_spec_writing_reference_doc.py:202-300`).
- `tests/meta/test_coverage_threshold_regressions.py` and `tests/meta/test_coverage_misc.py` are broad internal-helper coverage padding bundles. They explicitly target private helpers and cover many unrelated edge branches in config, presentation, feature-state, and checker internals rather than a coherent external contract (`tests/meta/test_coverage_threshold_regressions.py:3-4`, `tests/meta/test_coverage_threshold_regressions.py:67-145`, `tests/meta/test_coverage_threshold_regressions.py:873-1002`, `tests/meta/test_coverage_misc.py:3-4`, `tests/meta/test_coverage_misc.py:32-106`).
- Loop tests should not be deleted wholesale. The low-value loop work is concentrated in test-support/helper files and presentation-label assertions, such as helper-only support modules and exact output wording checks (`tests/loop/test_loop_feature_iteration_support.py:14-68`, `tests/loop/test_loop_feature_phase_progress_helpers.py:15-138`, `tests/loop/test_selected_feature_load_without_archive_fallback.py:11-44`, `tests/loop/test_loop_selection.py:120-251`, `tests/loop/test_loop_output.py:1108-1169`).
- The strongest retention anchors remain in behavior-facing suites: CLI surfaces in `tests/cli/test_cli.py:53-947`, loop lifecycle/execution/reviewers in `tests/loop/test_loop_feature_iteration_lifecycle.py:33-353`, `tests/loop/test_loop_feature_iteration_execution.py:32-599`, `tests/loop/test_loop_feature_iteration_verification.py:36-505`, `tests/loop/test_loop_reviewers.py:18-295`, checks runtime loading in `tests/checks/test_run_checks_contract_loader.py:14-250`, and git behavior in `tests/git/test_client.py:9-266` and `tests/git/test_git_client.py:18-551`.
- The suite shape today is: `meta` for migration and repo-policy guards, `fitness` for checker self-tests and architecture policing, `loop` for both behavior anchors and internal helper/presentation coverage, and `cli/git/config` for stronger behavior-facing anchors. FEAT-184 can therefore proceed in ordered deletion waves with a strong bias toward deleting whole files in `meta` and `fitness` first.

## Detailed Findings

### Suite composition and concentration of low-value tests
- The targeted directories are large enough that broad deletion can materially reduce maintenance: `tests/meta` has 14 Python files, `tests/fitness` has 39, and `tests/loop` has 26, while the more behavior-facing `tests/git` and `tests/config` areas are much smaller and more focused.
- The current low-value surface is concentrated in files that scan the repository tree, inspect source ASTs, assert exact documentation strings, or exercise private helper branches. Those patterns recur throughout `tests/meta` and `tests/fitness`.
- The core behavior anchors described in the spec are still mostly outside this delete set: CLI command behavior, runtime iteration flow, git client behavior, backend seams, and checks runtime orchestration are covered elsewhere in `tests/cli`, `tests/git`, `tests/config`, and the stronger loop flow files.

### Coverage and repository verification invariants
- `pyproject.toml:26-27` configures pytest with `--cov=engineeringagent --cov-report= --cov-fail-under=95 -n 2`, so FEAT-184 cannot rely on removing tests and then softening the repository gate.
- `tests/meta/test_validator.py:1781-1790` asserts that `--cov=engineeringagent` and `--cov-fail-under=95` stay in pytest addopts and that the suite does not hide behind a `not integration` default filter.
- `harness/checks.yaml:30-34` runs `uv run pytest -q` in the normal checks path, so the final implementation must satisfy both direct pytest and checks-driven validation.
- These three surfaces make full-suite execution and coverage preservation part of the current repository contract, not merely a best-effort implementation preference.

### High-confidence whole-file deletion candidates in `tests/meta`
- `tests/meta/test_legacy_shim_imports.py:9-39` only asserts that removed modules remain undiscoverable and raise import failures. This is a pure migration cleanup guard for legacy package names, not a behavior-facing contract.
- `tests/meta/test_no_gate_profile_references.py:18-63` recursively scans source, harness, docs, and README text for deprecated wording such as `gate_profile`, `gates run`, and `--profile`. It locks terminology and file content, not user behavior.
- `tests/meta/test_legacy_checks_import_guard.py:15-109` walks production ASTs to forbid old import paths and also asserts removed packages like `engineeringagent.fitness` and `engineeringagent.retry_feedback` stay gone. This is another migration-era structural guard.
- `tests/meta/test_agent_boundary_guards.py:39-118` enforces architecture boundaries by AST-scanning for `start_agent` references and `format="json"` usage outside allowed directories. It verifies implementation placement, not workflow outcomes.
- `tests/meta/test_agent_boundary_migration_smoke.py:114-147` contains similar boundary-preservation checks, including literal source-text assertions against specific imports. The file is mostly migration-shape enforcement.
- `tests/specs/test_specs_layout_smoke.py:23-90` belongs with the same deletion wave even though it is outside `tests/meta`: it asserts feature directory existence, forbids flat archived specs, and enforces plan-frontmatter status vocabulary across the repo.

### High-confidence whole-file deletion candidates in `tests/fitness`
- `tests/fitness/test_fitness_rules_repo_validators_boundary.py:6-28` only checks that a removed rule id is absent from the manifest and that a deleted checker file still does not exist.
- `tests/fitness/test_fitness_rules_test_layout_module_mirroring.py:56-110` synthesizes test/source paths to enforce mirrored naming and alias bans such as forbidding `tests/vcs/`. This is repository-shape governance rather than product behavior.
- `tests/fitness/test_fitness_rules_no_doc_content_tests.py:40-164` is meta-testing of test style: it creates fake tests and checks that a checker forbids reading docs content. This catches almost no user-visible regression.
- `tests/fitness/test_fitness_rules_source_first_loop_commands.py:72-592` is a large command-surface policing suite for exact command forms in spec verification, checks config, bundled plans, and documentation-adjacent surfaces. It is broad, brittle, and heavily tied to wording and command syntax policy.
- `tests/fitness/test_fitness_rules_harness_src_import_allowlist.py:29-111` loads a checker and validates an internal import allowlist for harness scripts. It is checker white-box coverage for architecture policy.
- `tests/fitness/test_fitness_rules_scaffold_template_locality.py:35-208` patches six private checker constants and then exercises the private `_scaffold_template_locality_violations(...)` helper with synthetic files. This is a strong white-box candidate for deletion rather than retention.

### Broad helper-coverage padding files
- `tests/meta/test_coverage_threshold_regressions.py:3-4` explicitly declares that it intentionally exercises private helpers, and the file then spans many unrelated internals across config parsing, ANSI detection, feature-state archive edge cases, gate/verification fallback paths, and command-adapter normalization.
- Early sections of that file cover tiny internal edge cases such as `_normalize_docs_root(...)`, `tty_supports_ansi(...)`, and compatibility shims between internal functions (`tests/meta/test_coverage_threshold_regressions.py:67-145`). These are implementation-coupled and fragmented.
- The same file later drills into adapter-private error handling and normalization internals rather than user-level fitness execution behavior (`tests/meta/test_coverage_threshold_regressions.py:873-1002`).
- `tests/meta/test_coverage_misc.py:3-4` does the same on a smaller scale: it targets helper behavior in path matching, subprocess argument construction, file logger creation, and commit-message helper loading (`tests/meta/test_coverage_misc.py:32-106`).
- Both files are strong FEAT-184 candidates because they exist largely to prop up branch coverage over internal seams, exactly the kind of coverage padding the spec calls out.

### Documentation and wording lock tests
- `tests/meta/test_spec_writing_reference_doc.py:130-300` is the most explicit wording-lock surface. It asserts exact phrases inside approach docs, examples, templates, and reviewer documentation, such as command examples, status vocabulary, and bundled-planning wording.
- The top of that file has one behavior-adjacent piece: `_feature_verification_commands(...)` aggregates verification commands from feature YAML and bundled plan phases, and `test_feature_verification_commands_include_bundled_plan_phases` verifies that mixed extraction behavior (`tests/meta/test_spec_writing_reference_doc.py:11-51`, `tests/meta/test_spec_writing_reference_doc.py:71-127`).
- Everything after that shifts into synchronization checks for prose and examples. This makes the file a good trim target even if a very small extraction-focused test is preserved elsewhere.

### Loop helper and presentation tests that are lower value than loop-flow anchors
- `tests/loop/test_loop_feature_iteration_support.py:14-68` only tests helper functions living under `tests/loop/feature_iteration_support.py`. This is test-support testing itself.
- `tests/loop/test_loop_feature_phase_progress_helpers.py:15-138` focuses on internal progress-unit normalization and invalid-plan fallback semantics via handcrafted fixtures. It is much narrower than actual loop-run behavior.
- `tests/loop/test_selected_feature_load_without_archive_fallback.py:11-44` directly imports the private `_load_selected_feature` helper and asserts a no-fallback path for an archived counterpart.
- `tests/loop/test_loop_selection.py:120-251` is mixed. The fallback behavior is meaningful, but several tests patch `build_selector_prompt` or `describe_action` and then assert exact step-label strings like `Selector step: ...`, which is presentation-coupled rather than behavioral.
- `tests/loop/test_loop_output.py:1108-1169` asserts exact emoji-and-text non-verbose terminal output lines for verification, reviewer status, failure wording, and phase progress context. These are brittle output contracts, not substantive runtime coverage.
- `tests/loop/test_loop_runtime_time_format.py:8-10` is a tiny single-helper formatting test. It is safe to delete unless the team wants to keep one direct unit test for UTC `Z` formatting.

### Mixed files where only selective trimming looks justified
- `tests/fitness/test_fitness_rules_checks_import_surface.py:34-341` mixes several weak tests with a smaller amount of real public-surface validation. The weaker parts are the ones that load checker internals and assert exact allowed-export sets or removed helper names. The more defensible part is the higher-level expectation that production modules import the top-level checks surface rather than deep checker internals.
- `tests/loop/test_loop_selection.py:139-197` has meaningful fallback behavior coverage when selector execution fails, but `tests/loop/test_loop_selection.py:199-221` is mostly a label-text assertion after patching `describe_action`.
- `tests/loop/test_loop_output.py:1108-1169` is presentation-heavy, but earlier sections in the same file record telemetry, reviewer status, and handoff persistence. Those earlier persistence-oriented tests are stronger than the final rendered-text assertions.
- `tests/cli/test_cli.py:280-449` includes several command-delegation tests that patch top-level handlers and assert exact stdout plus captured kwargs. Those are lower value than the command-surface and validation failure tests elsewhere in the file, but they do not look like first-wave delete targets compared with the stronger `meta` and `fitness` candidates.

### Retention anchors that do not look like FEAT-184 deletion targets
- The CLI suites still provide user-visible command behavior coverage, including help text, rejected flags, command registration, schema output, and checks command surfaces (`tests/cli/test_cli.py:53-279`, `tests/cli/test_cli.py:569-947`).
- Git tests remain behavior-facing and should act as anchors for repository-side effects and commit-message rules (`tests/git/test_client.py`, `tests/git/test_git_client.py`, `tests/git/test_commit_message_validation.py`).
- The stronger loop-flow files that exercise feature iteration lifecycle, execution, verification, feedback, reviewers, and runtime orchestration are much closer to the retained anchor set described by the FEAT-184 spec than the helper-only loop files are.
- `tests/checks/test_run_checks_contract_loader.py:14-250` is a stronger checks anchor than the fitness rule self-tests because it validates the public checks runtime loading and contract surface rather than a specific repository policy checker implementation.
- `tests/meta/test_validator.py:30-1802` should remain selectively retained even though it lives under `tests/meta`, because it covers schema/repository validation behavior and explicitly locks the repository coverage contract (`tests/meta/test_validator.py:1781-1790`).

## Code References
- `tests/meta/test_legacy_shim_imports.py:9-39` - legacy import and module-discoverability removal guards.
- `tests/meta/test_no_gate_profile_references.py:18-63` - recursive repo scan for deprecated wording and command references.
- `tests/meta/test_legacy_checks_import_guard.py:15-109` - AST import policing for removed legacy checks surfaces.
- `tests/meta/test_agent_boundary_guards.py:39-118` - AST boundary enforcement for `start_agent` and `format="json"`.
- `tests/meta/test_agent_boundary_migration_smoke.py:114-147` - migration smoke assertions around CLI bootstrap and old opencode imports.
- `tests/meta/test_spec_writing_reference_doc.py:71-127` - verification-command extraction behavior for flat features and bundled plans.
- `tests/meta/test_spec_writing_reference_doc.py:202-300` - exact wording synchronization checks across approach docs and reviewer docs.
- `tests/meta/test_coverage_threshold_regressions.py:67-145` - private-helper coverage around config and presentation edge paths.
- `tests/meta/test_coverage_threshold_regressions.py:873-1002` - adapter-private error-path and normalization coverage.
- `tests/meta/test_coverage_misc.py:32-106` - helper-oriented coverage for path matching, subprocess argument construction, logging, and commit message helpers.
- `pyproject.toml:26-27` - repository pytest coverage and parallelism contract.
- `harness/checks.yaml:30-34` - default repo checks path that runs the full pytest suite.
- `tests/meta/test_validator.py:1781-1790` - regression locking the declared pytest coverage gate.
- `tests/specs/test_specs_layout_smoke.py:23-90` - repository layout and bundled-plan vocabulary smoke coverage.
- `tests/fitness/test_fitness_rules_repo_validators_boundary.py:6-28` - removed rule and deleted checker presence guard.
- `tests/fitness/test_fitness_rules_test_layout_module_mirroring.py:56-110` - repository test-layout mirroring rule self-tests.
- `tests/fitness/test_fitness_rules_no_doc_content_tests.py:40-164` - checker self-tests for disallowing test reads of documentation content.
- `tests/fitness/test_fitness_rules_source_first_loop_commands.py:72-592` - command-form policing across feature verification, checks config, and bundled plans.
- `tests/fitness/test_fitness_rules_harness_src_import_allowlist.py:29-111` - harness checker tests for import allowlist boundaries.
- `tests/fitness/test_fitness_rules_scaffold_template_locality.py:35-208` - white-box checker tests patched through private constants and helper functions.
- `tests/loop/test_loop_feature_iteration_support.py:14-68` - tests for loop test-support helpers.
- `tests/loop/test_loop_feature_phase_progress_helpers.py:15-138` - progress helper normalization and invalid-plan fallback coverage.
- `tests/loop/test_selected_feature_load_without_archive_fallback.py:11-44` - private selected-feature helper no-fallback path.
- `tests/loop/test_loop_selection.py:120-251` - selector behavior mixed with prompt-label and fallback-output assertions.
- `tests/loop/test_loop_output.py:1108-1169` - exact non-verbose terminal output assertions for verification and phase progress.

## Architecture Documentation
The repository's tests currently split into four distinct roles. `tests/cli`, `tests/git`, `tests/config`, and the stronger loop lifecycle files act as behavior-facing anchors for user-visible commands, runtime flow, repository operations, and persisted configuration. `tests/meta` acts as a policy and migration bucket, with many files scanning source trees, imports, docs, and deleted paths. `tests/fitness` acts as a checker self-test bucket, often creating synthetic repos and asserting exact violations for architecture or layout rules. `tests/loop` mixes genuinely valuable runtime-flow coverage with lower-value helper, formatter, and support-fixture tests.

Within that structure, the lowest-value patterns are consistent: repository-shape locks, migration cleanup guards, wording synchronization, exact rendered-text assertions, and direct testing of private helper branches. Those patterns are most common in `tests/meta` and `tests/fitness`, then in a smaller subset of `tests/loop`. The architecture of the suite therefore already suggests an ordered cleanup strategy: remove whole-file policy and migration guards first, then remove white-box checker/helper coverage, then trim presentation-only assertions from mixed loop and CLI files while leaving behavior-facing orchestration coverage intact.

## Open Questions
- If the implementation deletes the broad helper-coverage bundles in `tests/meta/test_coverage_threshold_regressions.py` and `tests/meta/test_coverage_misc.py`, which remaining behavior-facing suites are expected to carry the coverage gate for the same production modules?
- For mixed files such as `tests/meta/test_spec_writing_reference_doc.py`, `tests/fitness/test_fitness_rules_checks_import_surface.py`, and `tests/loop/test_loop_output.py`, should FEAT-184 preserve the few behavior-adjacent tests by moving them elsewhere, or accept deleting those small anchors along with the brittle files if the full coverage gate still passes?
