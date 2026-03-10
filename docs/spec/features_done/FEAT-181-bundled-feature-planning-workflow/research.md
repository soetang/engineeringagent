---
date: 2026-03-09T10:14:27+00:00
researcher: OpenCode
git_commit: 6947f2f
branch: master
repository: soetang/engineeringagent
topic: "Research FEAT-181 bundled feature planning workflow"
tags: [research, specs, validation, loop-runtime, workflow]
status: complete
last_updated: 2026-03-09
last_updated_by: OpenCode
specification_path: docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow
---

# Research: Research FEAT-181 bundled feature planning workflow

## Research Question
Research `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml` following `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/research-session-approach.md` and document the current codebase state relevant to bundled per-feature planning artifacts with canonical `spec.yaml` ownership.

## Summary
- The current runtime and validator stack is still flat-file-first: active specs are discovered from direct children of `docs/spec/features/*.yaml`, and archived specs are direct children of `docs/spec/features_done/*.yaml`.
- The strict feature contract in code is still a single YAML document. `FeatureSpec` does not define `planning_tier` or `artifacts`, and current status values are `backlog`, `in_progress`, `done`, and `blocked`.
- FEAT-181 already exists as a bundled documentation package with `spec.yaml`, `plan.md`, starter session prompts, and draft format examples. Those files define the proposed package contract, but repository code does not currently consume them.
- Markdown plus YAML frontmatter already exists as a repository pattern for approach docs, but there is no current parser or validator for `plan.md` or `research.md` artifacts.
- Repository guidance, reviewer prompts, fitness rules, smoke tests, and metadata tests still reference the flat `docs/spec/features/*.yaml` layout, so the current assumption is shared well beyond the runtime loader.
- Observed behavior matches the code paths: `uv run engineeringagent validate` and `uv run engineeringagent validate --schema-only` both return `spec validation: ok` with the FEAT-181 bundle present, which is consistent with nested `spec.yaml` files not being part of current discovery.

## Detailed Findings

### Active Feature Discovery And Validation Are Flat-File Based
- Runtime auto-discovery resolves `docs/spec/features` and scans only `features_dir.glob("*.yaml")`, then keeps specs whose status is `backlog` or `in_progress` (`src/engineeringagent/loop_runtime/feature_state.py:106-121`).
- The shared helper used by repo validation, `iter_feature_files()`, also returns only `sorted(features_dir.glob("*.yaml"))` (`src/engineeringagent/specs.py:440-449`).
- Repo validation builds its active/archive view from `docs/spec/features`, `docs/spec/features_done`, and `docs/spec/potential_features.yaml`, then validates active and done files from those flat scans (`src/engineeringagent/checks/validate/repo_validators.py:192-223`).
- The loop CLI and output text still describe `run --all` as working from active feature files under `docs/spec/features`, and the startup banner explicitly says `docs/spec/features/*.yaml` (`src/engineeringagent/cli/typer.py:309-320`, `src/engineeringagent/loop.py:67-71`).

### Current Contract Is Still A Single YAML Feature File
- `FeatureSpec` is defined as the top-level schema for `docs/spec/features/*.yaml` and currently includes id, title, type, expected commit subject, status, priority, objective, context, constraints, implementation notes, acceptance, subtasks, and `updated_at` (`src/engineeringagent/specs.py:289-307`).
- Current feature status values are only `backlog`, `in_progress`, `done`, and `blocked` (`src/engineeringagent/specs.py:41-48`).
- There is no model-owned `planning_tier` field, no `artifacts` block, and no model layer for `plan.md` or `research.md` companion documents in the current spec contract (`src/engineeringagent/specs.py:289-307`, `src/engineeringagent/specs.py:499-563`).
- This means the FEAT-181 draft/example use of `status: pending` and companion artifact metadata is not part of the currently enforced active-feature schema if those files were discovered by the validator (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:5-6`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/spec-format-example.yaml:5-6`).

### File Identity And Archive Behavior Assume Flat Files
- Feature-id invariant checks extract the expected id token from the filename stem, compare it to the YAML `id`, and enforce global uniqueness across active and done specs (`src/engineeringagent/checks/validate/repo_policy_feature_ids.py:47-89`, `src/engineeringagent/checks/validate/repo_policy_feature_ids.py:176-214`).
- Repo validation flags any active spec with `status: done` and says it must be moved under `docs/spec/features_done/<same-filename>.yaml` (`src/engineeringagent/checks/validate/repo_validators.py:344-358`).
- Runtime archival uses the same filename under `features_done` and only accepts sources whose parent directory is the active `features` directory (`src/engineeringagent/loop_runtime/feature_state.py:150-167`, `src/engineeringagent/loop_runtime/feature_state.py:295-349`).
- Selection logic treats a feature as a path-backed YAML spec and can match selector output by full path, filename, or unique feature id (`src/engineeringagent/loop_runtime/selection.py:37-65`).

### Bundled FEAT-181 Documents Already Define The Proposed Package
- The FEAT-181 spec states the intended move from flat active files to `docs/spec/features/FEAT-xxx-.../spec.yaml`, with `spec.yaml` remaining canonical and companion artifacts linked through a deterministic `artifacts` block (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:8-20`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:38-49`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:61-68`).
- The FEAT-181 plan already defines artifact roles, proposed `planning_tier` values, tier-based requirements, canonical ownership boundaries, and the guidance/validation split for fresh-session behavior (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/plan.md:25-54`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/plan.md:55-127`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/plan.md:139-145`).
- The example bundled spec and example plan show the proposed `artifacts` block and Markdown-plus-frontmatter plan shape, including structured `phases` with per-phase `status` fields (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/spec-format-example.yaml:1-25`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-format-example.md:1-43`).
- The research and planning session approach files already encode the intended session boundaries: fresh session before planning, `spec.yaml` as canonical source, and `research.md` as required input when the tier requires it (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/research-session-approach.md:17-27`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/research-session-approach.md:104-189`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-session-approach.md:5-40`).

### Markdown Frontmatter Exists Elsewhere, But Not Yet For Plan Artifacts
- The approach-doc registry already parses YAML frontmatter from Markdown and requires an `approach_id`, so Markdown-plus-frontmatter is an existing repository pattern (`src/engineeringagent/approach/registry.py:67-125`).
- No current `src/` code references `plan.md`, `research.md`, or plan/research frontmatter parsing, which means FEAT-181 would introduce a new artifact-validation surface rather than extending an existing feature-spec loader.

### Repository Guidance And Tests Still Assume The Old Layout
- User and contributor guidance still instructs authors to create `docs/spec/features/<ID>.yaml` files, and documentation placement guidance still says specs live under `docs/spec/features/*.yaml` (`README.md:19-23`, `src/engineeringagent/approach/docs/specifications.md:12-15`, `src/engineeringagent/approach/docs/specifications.md:62-85`, `docs/references/documentation-practices.md:24-26`).
- Reviewer prompts still say to scan `docs/spec/features/*.yaml` to find the current spec when `feature_path` is not supplied, and they treat feature-spec changes as `docs/spec/features/*.yaml` changes (`harness/reviewers/prompts/intent_integrity_reviewer.md:10-22`).
- A metadata test still scans only `features_dir.glob("*.yaml")` when checking active feature verification commands (`tests/meta/test_spec_writing_reference_doc.py:15-27`).
- A fitness rule script still scans `docs/spec/features/*.yaml`, and the real OpenCode smoke rule writes and expects a flat active spec path `docs/spec/features/FEAT-001-hello-world-smoke.yaml` plus a flat archived file under `docs/spec/features_done/*.yaml` (`harness/fitness-functions/check_source_first_loop_commands.py:17-23`, `harness/fitness-functions/check_source_first_loop_commands.py:81-113`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:25-27`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:109-123`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:352-379`).

## Code References
- `src/engineeringagent/loop_runtime/feature_state.py:106-121` - active-feature auto-discovery scans only direct `*.yaml` files and filters by runnable statuses.
- `src/engineeringagent/specs.py:289-307` - current `FeatureSpec` model; no `planning_tier` or `artifacts` fields.
- `src/engineeringagent/specs.py:440-449` - shared feature-file iterator uses flat `glob("*.yaml")`.
- `src/engineeringagent/checks/validate/repo_validators.py:192-223` - repo validation roots and scan flow for active and done specs.
- `src/engineeringagent/checks/validate/repo_validators.py:344-358` - done active specs must be archived under `docs/spec/features_done`.
- `src/engineeringagent/checks/validate/repo_policy_feature_ids.py:47-89` - filename token to YAML id alignment for feature specs.
- `src/engineeringagent/loop_runtime/feature_state.py:150-167` - archive path resolution assumes flat active and done directories.
- `src/engineeringagent/loop_runtime/selection.py:37-65` - selector output parsing uses path, filename, and feature id.
- `src/engineeringagent/approach/registry.py:67-125` - existing Markdown frontmatter parsing pattern for approach docs.
- `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:61-68` - current FEAT-181 artifact map for plan, research, and supporting docs.
- `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/plan.md:96-127` - proposed discovery, tier rules, and ownership boundaries.
- `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-format-example.md:1-43` - example plan frontmatter with phases and per-phase status.
- `README.md:19-23` - current onboarding still points users to `docs/spec/features/<ID>.yaml`.
- `harness/reviewers/prompts/intent_integrity_reviewer.md:10-22` - reviewer prompt still assumes flat feature spec paths.

## Architecture Documentation
Current repository architecture treats the feature spec as one canonical YAML file that is both the runtime selection unit and the validation unit. Runtime discovery, archive movement, id/path invariants, reviewer fallback logic, tests, and user-facing docs all depend on flat `docs/spec/features/*.yaml` and `docs/spec/features_done/*.yaml` conventions rather than a folder package abstraction.

The FEAT-181 folder is currently documentation-only: it already describes a future package model where `spec.yaml` stays canonical, `plan.md` and `research.md` are colocated, and session hygiene is carried by guidance rather than validators. That package model is internally consistent across `spec.yaml`, `plan.md`, and the supporting examples, but it is not yet wired into runtime discovery or validation.

The closest existing implementation pattern for FEAT-181's proposed Markdown metadata is the approach-doc system, which already parses YAML frontmatter from Markdown files. By contrast, feature planning artifacts are not yet modeled or parsed in `src/engineeringagent`.

## Open Questions
- Should archived done features also become bundled feature folders, or should `docs/spec/features_done` remain a flat archive? FEAT-181's current plan leaves this unresolved (`docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/plan.md:156-160`).
- Should the feature status vocabulary stay aligned with the current code model (`backlog`, `in_progress`, `done`, `blocked`), or should the bundled-spec contract also change status terms to include `pending` as used in the FEAT-181 draft/example docs (`src/engineeringagent/specs.py:41-48`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml:5-6`)?
- How broad should the migration be for flat-path assumptions outside the core validator/runtime, including README guidance, reviewer prompts, smoke rules, and metadata tests (`README.md:19-23`, `harness/reviewers/prompts/intent_integrity_reviewer.md:10-22`, `harness/fitness-functions/check_real_opencode_hello_world_smoke.py:25-27`)?

## User Follow-Up
- Decide whether done-spec archival should stay flat or move to bundled folders.
- Decide whether FEAT-181 should preserve the current feature-status vocabulary or intentionally change it.
- Decide how much of the surrounding prompt/doc/test surface should move from flat file references to package-entrypoint references.
- Start a new session for the planning phase using `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml`, `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/research.md`, and `docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-session-approach.md`.
