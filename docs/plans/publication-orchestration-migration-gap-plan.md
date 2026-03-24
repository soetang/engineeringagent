---
schema_version: 1
task_id: port-missed-publication-orchestration-migration
title: Port the missed publication orchestration refactor from vibecoder PR #9
status: done
branch: feat/publication-orchestration-migration-port
base_branch: master
phases:
  - id: publication-boundary
    title: Add the missing publication orchestrator boundary
    status: done
  - id: content-ownership
    title: Move publication content generation out of version control
    status: done
  - id: runtime-composition
    title: Rewire application runtime to compose publication orchestration
    status: done
  - id: boundary-rules
    title: Tighten protocol and import boundaries around publication flow
    status: done
  - id: tests-and-cleanup
    title: Add publication-boundary tests and retire obsolete assumptions
    status: done
---

# Publication Orchestration Migration Gap Plan

## Goal

Port the missed publication orchestration refactor from `vibecoder` PR #9 into current `engineeringagent` `master` so that publication workflow ownership lives in orchestrators instead of application and version control.

## Context

The old `vibecoder` PR #9 was merged, but its changes were not carried into the renamed `engineeringagent` repository during migration.

Current `engineeringagent` still reflects the pre-refactor shape:

- `src/engineeringagent/application/observers/workspace_version_control_observer.py` still owns commit, push, and pull request workflow.
- `src/engineeringagent/application/workspace_runtime.py` still wires `VersionControlContentService` directly.
- `src/engineeringagent/version_control/content_service.py` and `content_models.py` still own publication content generation.
- `src/engineeringagent/orchestrators/publication/` does not exist.
- `harness/policy/import_rules.yaml` still uses the older, looser version-control and forge boundaries.

## Source Context For The Implementing Agent

If you are implementing this plan without prior conversation context, first review the original upstream refactor that was missed during migration.

### Primary upstream references

- PR overview: <https://github.com/soetang/vibecoder/pull/9>
- Files changed: <https://github.com/soetang/vibecoder/pull/9/files>
- Raw diff: <https://github.com/soetang/vibecoder/pull/9.diff>
- Raw patch: <https://github.com/soetang/vibecoder/pull/9.patch>
- Merge commit: <https://github.com/soetang/vibecoder/commit/610efcd679795d7819101710495547f162321e5d>
- Feature branch: <https://github.com/soetang/vibecoder/tree/feat/publication-orchestration-boundary>

### Highest-signal upstream commits

- Define publication orchestration models and ports: <https://github.com/soetang/vibecoder/commit/48cf991c0dbc6278c62db434fc90858612d957cf>
- Move publication content generation into orchestrators: <https://github.com/soetang/vibecoder/commit/a8748ec1c51da6251be6cec88bc1b5b732d6cc0b>
- Add publication observer for commit and PR orchestration: <https://github.com/soetang/vibecoder/commit/4b6485f588e5ffe0f81c5f35137944c6587bca9b>
- Centralize publication workflow in publication orchestrators: <https://github.com/soetang/vibecoder/commit/f5b00ab0240cb870f9719cc511e385d0fb9baf47>
- Refine publication dependency boundaries: <https://github.com/soetang/vibecoder/commit/36874f72e3db119e327f872ceb4311ede91f12ce>
- Move publication content policy into orchestrator: <https://github.com/soetang/vibecoder/commit/87d34a694b834a58391c4e9645188d310aa68960>
- Update loop tests for shared orchestrator models: <https://github.com/soetang/vibecoder/commit/24ee40c2bb6df8018ba3164a48f38074ef37eaa3>

### Most relevant upstream files to study

Focus first on these paths in the PR "Files changed" view:

- `src/developer/orchestrators/publication/__init__.py`
- `src/developer/orchestrators/publication/models.py`
- `src/developer/orchestrators/publication/protocols.py`
- `src/developer/orchestrators/publication/publication_observer.py`
- `src/developer/application/publication_runtime.py`
- `src/developer/application/workspace_runtime.py`
- `src/developer/agent_backends/adapters/publication_content_agent.py`
- `src/developer/prompts/renderer.py`
- `harness/policy/import_rules.yaml`
- `tests/orchestrators/publication/test_publication_observer.py`
- `tests/orchestrators/publication/test_models_and_protocols.py`

### Important adaptation note

Do not copy the upstream diff mechanically.

Translate `developer.*` paths into `engineeringagent.*`, and prefer adapting the refactor to the current repository structure described in this plan. In particular:

- reuse existing shared lifecycle types under `engineeringagent.orchestrators.loop` unless extraction is necessary;
- avoid duplicating existing low-level transport models from `engineeringagent.version_control.models` and `engineeringagent.forge.models`; and
- preserve the architectural intent even if some file names or package boundaries differ from upstream.

## Desired Outcome

After this migration:

- `engineeringagent.orchestrators.publication` owns commit, push, and PR workflow policy;
- `engineeringagent.version_control` owns only git mechanics and transport models;
- `engineeringagent.forge` owns only forge mechanics and transport models;
- `engineeringagent.application` acts only as a composition root for publication dependencies; and
- tests and import rules make the boundary difficult to regress.

## Explicit Port Decisions

To keep the migration aligned with the current codebase, use these decisions instead of copying PR #9 literally:

1. **Add `engineeringagent.orchestrators.publication`, but do not blindly add `orchestrators.shared`.**
   Reuse existing shared lifecycle types from `engineeringagent.orchestrators.loop.models` and `engineeringagent.orchestrators.loop.protocols` unless a concrete gap requires extraction.

2. **Move publication content/context models out of `version_control`, but do not duplicate low-level git and forge transport models unnecessarily.**
   Existing models in `src/engineeringagent/version_control/models.py` and `src/engineeringagent/forge/models.py` should remain the default transport types unless a publication-owned abstraction is clearly better.

3. **Split publication content generation ownership away from `engineeringagent.version_control`.**
   Prompt rendering and agent-backed content generation should be publication-facing dependencies composed by application, not logic owned by version control.

4. **Keep deterministic fallback behavior.**
   Commit-message and pull-request generation must retain stable fallback behavior when prompt rendering or agent execution fails.

5. **Adopt the cleanup behavior improvement from PR #9.**
   Successful no-forge publication should still destroy the workspace after completion.

## Non-Goals

- Reworking implementation-run planning beyond what is required for publication wiring.
- Redesigning git or forge adapters beyond making them satisfy publication-facing ports.
- Refactoring unrelated orchestrator packages.

## File-Oriented Scope

### New files expected

- `src/engineeringagent/orchestrators/publication/__init__.py`
- `src/engineeringagent/orchestrators/publication/models.py`
- `src/engineeringagent/orchestrators/publication/protocols.py`
- `src/engineeringagent/orchestrators/publication/publication_observer.py`
- `src/engineeringagent/application/publication_runtime.py`
- `src/engineeringagent/agent_backends/adapters/publication_content_agent.py`
- publication prompt-rendering support under `src/engineeringagent/prompts/`
- `tests/orchestrators/publication/test_publication_observer.py`
- optionally `tests/orchestrators/publication/test_models_and_protocols.py`

### Existing files expected to change

- `src/engineeringagent/application/workspace_runtime.py`
- `src/engineeringagent/application/observers/workspace_version_control_observer.py`
- `src/engineeringagent/version_control/content_service.py`
- `src/engineeringagent/version_control/content_models.py`
- `src/engineeringagent/version_control/protocol.py`
- `src/engineeringagent/forge/protocol.py`
- `src/engineeringagent/agent_backends/adapters/__init__.py`
- `src/engineeringagent/prompts/__init__.py`
- `harness/policy/import_rules.yaml`
- `tests/application/test_workspace_runtime.py`
- `tests/version_control/test_content_service.py`

## Phase 1: Add the missing publication orchestrator boundary

### Checklist

- [ ] Add `src/engineeringagent/orchestrators/publication/`
- [ ] Add publication-owned models for commit/PR content and publication state
- [ ] Add publication-facing protocols for version control, forge, prompt rendering, content generation, state persistence, run metadata, and workspace cleanup
- [ ] Add an orchestrator-owned publication observer implementing the existing lifecycle observer contract
- [ ] Keep the publication package free of infrastructure adapter imports

### Target files

- `src/engineeringagent/orchestrators/publication/__init__.py`
- `src/engineeringagent/orchestrators/publication/models.py`
- `src/engineeringagent/orchestrators/publication/protocols.py`
- `src/engineeringagent/orchestrators/publication/publication_observer.py`

### Notes

Prefer reusing `ImplementationContext`, `IterationArtifact`, `RunPublicationResult`, and `ImplementationLifecycleObserver` from the current loop boundary unless that causes awkward coupling.

## Phase 2: Move publication content generation out of version control

### Checklist

- [ ] Stop treating `VersionControlContentService` as the owner of commit and PR content generation
- [ ] Move or replace `CommitPromptContext` and `PullRequestPromptContext` with publication-owned models
- [ ] Add a publication-facing prompt renderer outside `engineeringagent.version_control`
- [ ] Add an agent-backed publication content adapter outside `engineeringagent.version_control`
- [ ] Preserve deterministic fallback generation behavior in the publication observer path

### Target files

- `src/engineeringagent/version_control/content_service.py`
- `src/engineeringagent/version_control/content_models.py`
- `src/engineeringagent/agent_backends/adapters/publication_content_agent.py`
- `src/engineeringagent/agent_backends/adapters/__init__.py`
- publication prompt-rendering support under `src/engineeringagent/prompts/`
- `src/engineeringagent/prompts/__init__.py`

### Notes

The key architectural goal of this phase is to remove the `version_control -> agent_backends` ownership leak.

## Phase 3: Rewire application runtime to compose publication orchestration

### Checklist

- [ ] Add application-owned adapters for publication state persistence, run metadata persistence, and workspace lifecycle cleanup
- [ ] Update `workspace_runtime.py` to build `PublicationObserver` instead of `WorkspaceVersionControlObserver`
- [ ] Inject selected version control, forge, prompt rendering, and content generation implementations through publication-owned ports
- [ ] Remove publication workflow decisions from application-owned modules
- [ ] Ensure successful no-forge publication still performs workspace cleanup

### Target files

- `src/engineeringagent/application/publication_runtime.py`
- `src/engineeringagent/application/workspace_runtime.py`
- `src/engineeringagent/application/observers/workspace_version_control_observer.py`

### Notes

Application may still choose concrete dependencies. It must not own commit/push/PR sequencing or publication content policy.

## Phase 4: Tighten protocol and import boundaries around publication flow

### Checklist

- [ ] Make `VersionControlProtocol` satisfy the publication version-control port
- [ ] Make `ForgeProtocol` satisfy the publication forge port
- [ ] Add `orchestrators-publication-boundary`
- [ ] Tighten `version-control-boundary` so it no longer owns prompt-backed agent generation
- [ ] Tighten `forge-boundary` so it depends only on publication-facing contracts and config

### Target files

- `src/engineeringagent/version_control/protocol.py`
- `src/engineeringagent/forge/protocol.py`
- `harness/policy/import_rules.yaml`

### Notes

Keep existing low-level transport models where possible. The important change is boundary ownership, not model churn for its own sake.

## Phase 5: Add publication-boundary tests and retire obsolete assumptions

### Checklist

- [ ] Add `tests/orchestrators/publication/test_publication_observer.py`
- [ ] Add tests for commit skip when there are no changes
- [ ] Add tests for deterministic commit-generation fallback behavior
- [ ] Add tests for push-only publication when forge is disabled
- [ ] Add tests for PR reuse versus PR creation
- [ ] Update workspace runtime composition tests for the new observer wiring
- [ ] Move or replace tests that assume `version_control` owns prompt-backed publication content generation

### Target files

- `tests/orchestrators/publication/test_publication_observer.py`
- optionally `tests/orchestrators/publication/test_models_and_protocols.py`
- `tests/application/test_workspace_runtime.py`
- `tests/version_control/test_content_service.py`

### Notes

The primary behavior tests should sit at the publication orchestrator boundary, not at the version-control content-service boundary.

## Acceptance Criteria

The migration is complete when all of the following are true:

- `engineeringagent.orchestrators.publication` exists and owns publication workflow policy.
- `engineeringagent.application.workspace_runtime` composes publication dependencies without owning workflow logic.
- `engineeringagent.version_control` no longer owns prompt-backed commit/PR generation.
- `engineeringagent.version_control` does not need to import agent backend protocols to satisfy publication behavior.
- import rules encode the new dependency direction.
- publication observer tests cover commit, push, PR reuse/create, fallback, and cleanup behavior.

## Suggested Execution Order

1. add the publication package and its ports/models;
2. add application publication runtime adapters;
3. move publication content-generation ownership out of `version_control`;
4. port the observer workflow into `orchestrators.publication`;
5. rewire `workspace_runtime.py` to compose the new observer;
6. remove or retire the old application observer and old content-service assumptions;
7. tighten import rules and protocol inheritance;
8. update tests around the new boundary.

## Risks And Mitigations

- **Risk:** copying PR #9 too literally introduces unnecessary churn.  
  **Mitigation:** reuse existing loop shared types and current transport models unless a real gap appears.

- **Risk:** content-generation ownership moves in name only while `version_control` still effectively owns it.  
  **Mitigation:** ensure prompt rendering and agent-backed content generation are wired through publication-facing ports.

- **Risk:** application remains the de facto orchestrator.  
  **Mitigation:** keep application responsible only for assembly, with all publication decisions living in `PublicationObserver`.

- **Risk:** migration updates behavior but not safeguards.  
  **Mitigation:** land import-rule changes and orchestrator-boundary tests in the same slice.
