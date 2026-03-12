# Fitness Rule Catalog

This file is generated from active manifest-declared fitness rules.

## Active Rules

| Rule ID | Severity | Adapter | Source | Scope | Config File | Summary |
| --- | --- | --- | --- | --- | --- | --- |
| `architecture.adapter-root-locality` | error | command | custom | `src/engineeringagent/adapters` | - | Keep adapter implementation modules inside focused adapters subpackages. |
| `architecture.agents-backends-boundary` | error | command | custom | `src/engineeringagent` | - | Forbid direct backend package usage outside the agents boundary. |
| `architecture.application-filesystem-boundary` | error | command | custom | `src/engineeringagent/application` | - | Keep direct filesystem mutations out of application modules. |
| `architecture.application-module-layout` | error | command | custom | `src/engineeringagent/application/*.py` | - | Keep the application package root limited to workflow-service modules. |
| `architecture.application-output-boundary` | error | command | custom | `src/engineeringagent/application` | - | Keep direct terminal output out of application modules. |
| `architecture.application-root-workflow-surface` | error | command | custom | `src/engineeringagent/application/__init__.py, src/engineeringagent/application/feature_iteration/__init__.py, plus repository imports of engineeringagent.application and engineeringagent.application.feature_iteration` | - | Keep engineeringagent.application focused on workflow services and forbid barrel re-exports for feature-iteration internals. |
| `architecture.application-subprocess-boundary` | error | command | custom | `src/engineeringagent/application` | - | Keep subprocess imports out of application modules. |
| `architecture.application-tests-boundary` | error | command | custom | `tests/application` | - | Keep application tests on application/domain/ports contracts instead of legacy checks internals. |
| `architecture.backend-literal-locality-budget` | error | command | custom | `src/engineeringagent excluding src/engineeringagent/adapters/agents/** and src/engineeringagent/checks/**` | `harness/fitness_functions/policies/backend_literal_locality_budget.yaml` | Enforce a zero-budget backend literal locality boundary outside allowed packages. |
| `architecture.bootstrap-runtime-surface` | error | command | custom | `src/engineeringagent/bootstrap/__init__.py` | - | Keep the bootstrap package from proxying adapter runtime exports. |
| `architecture.checks-import-surface` | error | command | custom | `src/engineeringagent` | - | Enforce a narrow import surface for engineeringagent.checks. |
| `architecture.checks-own-prompt-feedback-rendering` | error | command | custom | `src/engineeringagent/loop_runtime/**, src/engineeringagent/adapters/runtime/iteration_phases.py, src/engineeringagent/loop.py, and src/engineeringagent/prompts/renderer.py` | - | Fail when loop/prompt code performs checks-specific feedback shaping outside checks strategies. |
| `architecture.dep-directionality` | error | command | custom | `src/engineeringagent` | `harness/fitness_functions/policies/dependency_directionality.yaml` | Enforce ports-and-adapters dependency direction boundaries across presentation, application, ports, and domain seams. |
| `architecture.guidance-module-locations` | error | command | custom | `src/engineeringagent guidance adapter and CLI modules` | - | Keep guidance adapter and CLI modules in the target architecture paths. |
| `architecture.harness-root-yaml-only` | error | command | custom | `harness/ (regular files at root)` | - | Enforce YAML-only regular files directly under harness root. |
| `architecture.harness-src-import-allowlist` | error | command | custom | `harness/fitness_functions` | - | Restrict harness fitness functions to a narrow supported engineeringagent surface. |
| `architecture.hermetic-fitness-test-isolation` | error | command | custom | `tests/fitness` | `harness/fitness_functions/policies/hermetic_fitness_test_isolation.yaml` | Prevent tests/fitness from scanning the live repository checkout. |
| `architecture.init-cli-support-location` | error | command | custom | `src/engineeringagent/bootstrap/init_cli_support.py plus deleted root-level CLI helper modules` | - | Keep init CLI support wiring out of the package root. |
| `architecture.iteration-pipeline-observer-decoupling` | error | command | custom | `src/engineeringagent/application/feature_iteration/pipeline.py` | - | Keep iteration pipeline free of telemetry and console side effects. |
| `architecture.legacy-run-loop-bridge-absent` | error | command | custom | `src/engineeringagent/ports/run_loop_executor.py and deleted source files under src/engineeringagent/adapters/loop` | - | Keep the deleted loop adapter package removed. |
| `architecture.loop-checks-policy-ownership` | error | command | custom | `src/engineeringagent/loop_runtime/**, src/engineeringagent/adapters/runtime/iteration_phases.py, and src/engineeringagent/loop.py` | - | Fail when loop runtime encodes checks group/timing selection policy. |
| `architecture.loop-checks-result-boundary` | error | command | custom | `src/engineeringagent/loop_runtime/**, src/engineeringagent/adapters/runtime/iteration_phases.py, and src/engineeringagent/loop.py` | - | Fail when loop runtime branches on checks type/group semantics or parses checks-internal payloads. |
| `architecture.loop-facade-line-budget` | error | command | custom | `src/engineeringagent/loop.py` | - | Enforce a permanent line budget cap for the loop facade. |
| `architecture.loop-subprocess-boundary` | error | command | custom | `src/engineeringagent` | `harness/fitness_functions/policies/loop_subprocess_boundary_policy.yaml` | Enforce subprocess allowlist boundaries for command adapters/clients. |
| `architecture.markdown-locality-reference-coverage` | error | command | custom | `repository markdown (*.md)` | - | Restrict markdown to approved paths and require non-doc markdown files to be referenced in-repo (excluding prompt/scaffold template asset roots). |
| `architecture.module-statement-budget` | error | command | custom | `src/engineeringagent, harness, and tests` | `harness/fitness_functions/policies/module_statement_budget_policy.yaml` | Enforce AST-based non-doc statement caps for Python modules. |
| `architecture.no-doc-content-tests` | error | command | custom | `tests` | - | Prevent pytest from asserting exact wording in README/docs markdown. |
| `architecture.no-env-key-reads` | error | command | custom | `src/ harness/ tests/` | - | Forbid env-key reads (os.getenv, os.environ.get, os.environ['X'], 'X' in os.environ). |
| `architecture.no-facade-varargs-shims` | error | command | custom | `src/engineeringagent` | - | Block facade varargs shims, __signature__ masking, and hidden kwargs dropping. |
| `architecture.no-non-ignorable-ruff-suppressions` | error | command | custom | `src tests harness` | `harness/fitness_functions/policies/no_non_ignorable_ruff_suppressions.yaml` | Block suppression directives for configured high-value Ruff rules. |
| `architecture.no-pure-wrapper-functions` | error | command | custom | `src/engineeringagent and harness/fitness_functions` | `harness/fitness_functions/policies/no_pure_wrapper_functions.yaml` | Block pure pass-through wrappers and keep wrapper exceptions explicit. |
| `architecture.no-stdlib-dataclasses-in-src` | error | command | custom | `src/engineeringagent` | - | Block stdlib dataclasses usage in production source models. |
| `architecture.progress-log-path-locality` | error | command | custom | `src/engineeringagent` | - | Centralize loop progress artifact paths and writes behind approved helpers. |
| `architecture.prompt-locality` | error | command | custom | `src/engineeringagent` | - | Keep canonical loop prompt content and template reads localized. |
| `architecture.repo-config-presence` | error | command | custom | `engineeringagent.toml at repository root` | - | Require the canonical engineeringagent.toml file at the repository root. |
| `architecture.repo-layer-contracts` | error | command | custom | `src/engineeringagent package structure, legacy path deletions, and agent boundary surfaces` | - | Enforce repository-owned architecture contracts as fitness checks instead of validate-time unit rules. |
| `architecture.scaffold-template-locality` | error | command | custom | `src/engineeringagent` | - | Keep scaffold template payloads in scaffold_templates assets. |
| `architecture.shared-kernel-locality` | error | command | custom | `src/engineeringagent/domain/shared plus legacy duplicate-definition surfaces` | - | Localize cross-domain identifiers and enums under engineeringagent.domain.shared. |
| `architecture.source-first-loop-command-policy` | error | command | custom | `feature-package verification under the configured specifications root, bundled plan.md phases/examples, packaged plan-session/research-session guidance, contributor approach docs, loop implementation prompt template, docs/fixtures/real_opencode_hello_world_plan_template.md, and harness/checks.yaml` | - | Enforce source-first workspace execution for loop command surfaces. |
| `architecture.test-layout-module-mirroring` | error | command | custom | `tests` | `harness/fitness_functions/policies/test_layout_module_mirroring.yaml` | Enforce module-mirroring test structure and explicit test-layout exceptions. |
| `quality.purge-invariant` | error | command | custom | `tracked repository files excluding docs/specifications/features_done/ and .engineeringagent/progress/` | - | Keep removed identifiers out of tracked repository files. |
| `smoke.opencode-real-hello-world` | error | command | custom | `repository (temp repo)` | - | Validate the real agent loop end-to-end in an isolated temp repository. |

## Rule Details

### `architecture.adapter-root-locality`

- Name: Adapter root locality
- Side-effect free: `true`
- Rationale: Prevents the adapters package root from becoming a mixed implementation bucket and moves adapter code toward the target architecture layout.
- Remediation: Move root-level adapter implementation files into a focused subpackage under engineeringagent.adapters/.

### `architecture.agents-backends-boundary`

- Name: Agents/backends boundary
- Side-effect free: `true`
- Rationale: Keeps backend implementations an internal detail behind engineeringagent.adapters.agents.run_agent.
- Remediation: Replace direct backend package imports with engineeringagent.adapters.agents.run_agent.

### `architecture.application-filesystem-boundary`

- Name: Application filesystem boundary
- Side-effect free: `true`
- Rationale: Application workflows should orchestrate through ports and injected dependencies instead of mutating repository files directly.
- Remediation: Remove direct Path mutation calls from application modules and push file writes, deletes, renames, and directory creation into adapters or injected dependency callables.

### `architecture.application-module-layout`

- Name: Application module layout
- Side-effect free: `true`
- Rationale: The target architecture keeps orchestration entrypoints at the application root and pushes workflow-specific helpers into explicit subpackages so root-level legacy helper sprawl does not return.
- Remediation: Delete legacy flat helper modules from engineeringagent.application or move them into an explicit subpackage such as engineeringagent.application.feature_iteration.

### `architecture.application-output-boundary`

- Name: Application output boundary
- Side-effect free: `true`
- Rationale: Application workflows should return typed data and leave terminal rendering to bootstrap or presentation-owned callbacks.
- Remediation: Remove direct print calls from application modules and route output through injected runtime or presentation callbacks.

### `architecture.application-root-workflow-surface`

- Name: Application root workflow surface
- Side-effect free: `true`
- Rationale: The target architecture gives feature-iteration contracts and helpers explicit owning modules, so neither the application root nor engineeringagent.application.feature_iteration should act as compatibility facades.
- Remediation: Import public feature-iteration request/result models from engineeringagent.application.feature_iteration_service, import internal workflow helpers from their defining modules, and remove re-exports from engineeringagent.application.__init__ and engineeringagent.application.feature_iteration.__init__.

### `architecture.application-subprocess-boundary`

- Name: Application subprocess boundary
- Side-effect free: `true`
- Rationale: Application workflows should orchestrate through ports and injected runtime seams instead of classifying subprocess failures or timeouts directly.
- Remediation: Remove subprocess imports from engineeringagent.application and move process execution or failure formatting into adapters, ports, or injected runtime helpers.

### `architecture.application-tests-boundary`

- Name: Application tests boundary
- Side-effect free: `true`
- Rationale: Application-layer tests should exercise the target architecture seams directly so the migration can delete legacy checks surfaces without preserving test-only coupling.
- Remediation: Replace engineeringagent.checks imports in tests/application with engineeringagent.application, engineeringagent.domain.quality, and engineeringagent.ports contracts.

### `architecture.backend-literal-locality-budget`

- Name: Backend literal locality budget
- Config file: `harness/fitness_functions/policies/backend_literal_locality_budget.yaml`
- Side-effect free: `true`
- Rationale: Keeps backend-coupling tokens localized to backend-owned modules and checks adapters.
- Remediation: Remove backend-specific literals from core modules or move backend-specific behavior under engineeringagent.adapters.agents or engineeringagent.checks.

### `architecture.bootstrap-runtime-surface`

- Name: Bootstrap runtime surface
- Side-effect free: `true`
- Rationale: Bootstrap should expose bootstrap-owned composition helpers only instead of re-exporting adapter runtime internals through a legacy compatibility surface.
- Remediation: Remove adapter-runtime re-exports from engineeringagent.bootstrap.__init__ and import adapter runtime helpers from engineeringagent.adapters.runtime at their true ownership boundary.

### `architecture.checks-import-surface`

- Name: Checks import surface
- Side-effect free: `true`
- Rationale: Prevents production modules from depending on checks submodule internals that are not part of the supported stable API.
- Remediation: Replace engineeringagent.checks.<submodule> imports with allowed top-level names from engineeringagent.checks.

### `architecture.checks-own-prompt-feedback-rendering`

- Name: Checks-owned prompt feedback rendering
- Side-effect free: `true`
- Rationale: Keeps checks failure feedback rendering owned by checks strategies so loop and prompt wiring only forward prompt_feedback.
- Remediation: Remove loop/prompt checks-specific feedback builders and pass run_checks(...).prompt_feedback through unchanged.

### `architecture.dep-directionality`

- Name: Dependency directionality
- Config file: `harness/fitness_functions/policies/dependency_directionality.yaml`
- Side-effect free: `true`
- Rationale: Keeps presentation, application, ports, and domain modules aligned with the target architecture while isolating bootstrap and adapters as outer layers.
- Remediation: Refactor imports to preserve the declared layer boundaries: presentation depends inward, application uses ports/domain only, ports stay contract-only, and domain stays isolated.

### `architecture.guidance-module-locations`

- Name: Guidance module locations
- Side-effect free: `true`
- Rationale: Moves guidance code toward the target documents adapter package and the target presentation CLI module name while preventing legacy guidance paths from drifting back in.
- Remediation: Keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI surface under engineeringagent.presentation.cli.guidance; do not restore the legacy packaged-guidance module, adapters.guidance package, or presentation.cli.approach module.

### `architecture.harness-root-yaml-only`

- Name: Harness root YAML-only
- Side-effect free: `true`
- Rationale: Keeps harness root manifest-only and prevents executable/policy file sprawl at repository root policy surfaces.
- Remediation: Move non-YAML root files under harness/fitness_functions or another harness subdirectory; keep only *.yaml/*.yml files at harness root.

### `architecture.harness-src-import-allowlist`

- Name: Harness-to-src import allowlist
- Side-effect free: `true`
- Rationale: Prevents harness scripts from depending on orchestration/runtime internals that are not part of the supported authoring API.
- Remediation: Replace forbidden imports with the supported helpers under engineeringagent.checks.*.

### `architecture.hermetic-fitness-test-isolation`

- Name: Hermetic fitness test isolation
- Config file: `harness/fitness_functions/policies/hermetic_fitness_test_isolation.yaml`
- Side-effect free: `true`
- Rationale: Keeps pytest focused on synthetic fixture behavior while reserving real-repo compliance for harness and gate execution.
- Remediation: Pass a synthetic temp fixture as the checker project root/cwd and keep any real-repo cases in the explicit integration allowlist.

### `architecture.init-cli-support-location`

- Name: Init CLI support location
- Side-effect free: `true`
- Rationale: The target architecture keeps adapter-facing CLI support wiring in bootstrap instead of at the package root.
- Remediation: Keep init CLI support under engineeringagent.bootstrap and do not restore the root-level engineeringagent.init_cli_support module.

### `architecture.iteration-pipeline-observer-decoupling`

- Name: Iteration pipeline observer decoupling
- Side-effect free: `true`
- Rationale: Preserves the report-plus-observer split so orchestration remains testable and side effects stay localized.
- Remediation: Move telemetry and console output calls out of application.feature_iteration.pipeline and into loop-wired observers that consume IterationReport.

### `architecture.legacy-run-loop-bridge-absent`

- Name: Legacy run-loop bridge absent
- Side-effect free: `true`
- Rationale: The target architecture keeps transitional runtime execution inside the focused adapters.runtime package and does not retain a dedicated adapters.loop package.
- Remediation: Keep runtime loop execution wiring under engineeringagent.adapters.runtime.execution and do not restore the deleted engineeringagent.adapters.loop package.

### `architecture.loop-checks-policy-ownership`

- Name: Loop/checks policy ownership
- Side-effect free: `true`
- Rationale: Keeps loop runtime phase-driven while checks owns check-group and timing selection decisions.
- Remediation: Remove loop-owned checks group maps/literals and explicit checks policy kwargs; call run_checks with phase context only.

### `architecture.loop-checks-result-boundary`

- Name: Loop/checks result boundary
- Side-effect free: `true`
- Rationale: Keeps loop orchestration decoupled from checks internals so check-type-specific behavior stays in checks strategies.
- Remediation: Consume only checks run result fields ok/output/prompt_feedback in loop runtime and remove checks-internal decision/payload parsing.

### `architecture.loop-facade-line-budget`

- Name: Loop facade line budget
- Side-effect free: `true`
- Rationale: Keeps engineeringagent.loop concise as the compatibility facade seam.
- Remediation: Move non-control-flow internals into engineeringagent.loop_runtime modules.

### `architecture.loop-subprocess-boundary`

- Name: Loop subprocess boundary
- Config file: `harness/fitness_functions/policies/loop_subprocess_boundary_policy.yaml`
- Side-effect free: `true`
- Rationale: Centralizes command execution paths for consistent control.
- Remediation: Move OpenCode command execution to engineeringagent.adapters.agents.opencode.client and Git command execution to engineeringagent.adapters.vcs.git_cli.

### `architecture.markdown-locality-reference-coverage`

- Name: Markdown locality and reference coverage
- Side-effect free: `true`
- Rationale: Prevents markdown sprawl and orphaned non-doc markdown assets across repository zones while allowing internal template assets to remain self-contained.
- Remediation: Move markdown under approved roots and add at least one deterministic in-repo reference for each eligible markdown file outside docs/ (excluding src/engineeringagent/prompts/templates/, src/engineeringagent/scaffold_templates/, and backend scaffold templates).

### `architecture.module-statement-budget`

- Name: Module statement budget
- Config file: `harness/fitness_functions/policies/module_statement_budget_policy.yaml`
- Side-effect free: `true`
- Rationale: Limits module sprawl using executable structure so review and retrieval stay cohesive as packages evolve.
- Remediation: Reduce duplicated control-flow before splitting; extract cohesive concerns into existing folders first, or into a clearly named domain subpackage when needed; avoid root-level helper sprawl; for tests, prefer fixtures/builders/parametrization over repeated setup/assertions.

### `architecture.no-doc-content-tests`

- Name: No doc-content tests
- Side-effect free: `true`
- Rationale: Doc wording is intentionally flexible; tests should cover functionality instead.
- Remediation: Delete or refactor tests that read README.md or docs/**/*.md and assert substrings.

### `architecture.no-env-key-reads`

- Name: No env-key reads
- Side-effect free: `true`
- Rationale: Environment variable config is ad-hoc and hard to discover; configuration must come from engineeringagent.toml.
- Remediation: Remove env-key reads; load configuration from engineeringagent.toml (with pyproject fallback) and pass explicit values through contracts.

### `architecture.no-facade-varargs-shims`

- Name: No facade varargs shims
- Side-effect free: `true`
- Rationale: Keeps loop orchestration contracts explicit and typed instead of compatibility shims.
- Remediation: Replace varargs facade wrappers with explicit typed contracts and remove hidden kwargs dropping.

### `architecture.no-non-ignorable-ruff-suppressions`

- Name: No non-ignorable Ruff suppressions
- Config file: `harness/fitness_functions/policies/no_non_ignorable_ruff_suppressions.yaml`
- Side-effect free: `true`
- Rationale: Keep lint policy enforceable by requiring refactor-first remediation.
- Remediation: Remove inline/file-level ignore directives and refactor; for PLR0913, group related arguments into a NamedTuple or pydantic model.

### `architecture.no-pure-wrapper-functions`

- Name: No pure wrapper functions
- Config file: `harness/fitness_functions/policies/no_pure_wrapper_functions.yaml`
- Side-effect free: `true`
- Rationale: Keeps architecture boundaries direct by default and prevents seam-only indirection.
- Remediation: Remove pass-through wrappers, call canonical functions directly, and only add explicit allowlist exceptions with rationale when unavoidable.

### `architecture.no-stdlib-dataclasses-in-src`

- Name: No stdlib dataclasses in src
- Side-effect free: `true`
- Rationale: Enforces a single Pydantic BaseModel contract in src/engineeringagent.
- Remediation: Replace stdlib dataclasses usage with pydantic.BaseModel models.

### `architecture.progress-log-path-locality`

- Name: Progress log path locality
- Side-effect free: `true`
- Rationale: Prevents regressions that reintroduce inline progress/log path literals or direct file writes.
- Remediation: Construct paths via engineeringagent.adapters.progress.paths and write loop log sinks via engineeringagent.adapters.progress.filesystem_journal.

### `architecture.prompt-locality`

- Name: Prompt locality
- Side-effect free: `true`
- Rationale: Prevents prompt drift and duplicate canonical wording across modules.
- Remediation: Move canonical prompt text and template reads to engineeringagent.prompts templates/renderer modules.

### `architecture.repo-config-presence`

- Name: Repository config presence
- Side-effect free: `true`
- Rationale: The target architecture makes engineeringagent.toml the primary repository configuration surface so operators can inspect one dedicated file for defaults instead of relying on pyproject fallback.
- Remediation: Commit engineeringagent.toml at the repository root and keep it current with the repository's effective defaults.

### `architecture.repo-layer-contracts`

- Name: Repository layer contracts
- Side-effect free: `true`
- Rationale: Keeps structural package and boundary enforcement in the fitness-function system described by the target architecture while leaving validate focused on source documents and static config contracts.
- Remediation: Refactor the violating module or delete the restored legacy path so repository structure stays aligned with the target ports-and-adapters package layout.

### `architecture.scaffold-template-locality`

- Name: Scaffold template locality
- Side-effect free: `true`
- Rationale: Prevents init scaffold regressions from drifting back to inline template payloads in source modules.
- Remediation: Move scaffold template bodies to engineeringagent.scaffold_templates assets and load them via engineeringagent.bootstrap.init_scaffold.

### `architecture.shared-kernel-locality`

- Name: Shared-kernel locality
- Side-effect free: `true`
- Rationale: Keeps shared-kernel language in one canonical package instead of duplicating feature and check enums across legacy surfaces.
- Remediation: Move cross-domain identifiers and enums to engineeringagent.domain.shared and import them from there instead of redefining them elsewhere.

### `architecture.source-first-loop-command-policy`

- Name: Source-first loop command policy
- Side-effect free: `true`
- Rationale: Prevent stale cached package artifacts from bypassing current workspace source.
- Remediation: Replace forbidden in-repo uvx self-invocations and legacy module-form CLI commands with source-first forms; prefer uv run engineeringagent ...

### `architecture.test-layout-module-mirroring`

- Name: Test layout module mirroring
- Config file: `harness/fitness_functions/policies/test_layout_module_mirroring.yaml`
- Side-effect free: `true`
- Rationale: Replaces per-topic migration assertions with a single deterministic policy that keeps tests aligned to source ownership boundaries.
- Remediation: Move tests into mirrored module paths under tests/, or enumerate explicit exceptions for repository-level test policy surfaces.

### `quality.purge-invariant`

- Name: Purge invariant
- Side-effect free: `true`
- Rationale: Keeps repository cleanup enforcement in the fitness-function system instead of the validate lane so repository-wide scans run through declared quality policy.
- Remediation: Remove the forbidden token from tracked files or delete the restored legacy artifact. Progress artifacts under .engineeringagent/progress/ remain excluded.

### `smoke.opencode-real-hello-world`

- Name: Real OpenCode hello-world smoke
- Side-effect free: `true`
- Rationale: Catches regressions where the OpenCode subprocess/loop stops mid-implementation.
- Remediation: Enable via engineeringagent.toml ([harness.fitness] opencode-real-smoke = true) and resolve reported loop/setup errors.
