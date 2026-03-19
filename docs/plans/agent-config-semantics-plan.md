# Agent Config Semantics Plan

## Goal

Make agent configuration mean the same thing across backends so that any valid `[agents]` config is interpreted correctly.

In particular:

- `profile` should mean a broader backend preset or agent profile, which may bundle model choice, tools, prompts, and permissions;
- `model` should mean the underlying LLM only;
- backend adapters should map those fields to their own CLI flags without changing the meaning; and
- invalid backend-specific combinations should fail clearly.

## Current Problem

Today the shared settings surface is:

- `backend`
- `profile`
- `model`

But the backends do not interpret those fields the same way.

### Current Behavior

- `src/developer/agents/settings.py` defines `profile` and `model` as generic agent settings.
- `src/developer/agents/select_agent_service.py` forwards those values unchanged to every adapter.
- `src/developer/agents/adapters/codex_adapter.py` maps `model` to `codex --model` and `profile` to Codex profile resolution.
- `src/developer/agents/adapters/vibe_adapter.py` maps `model` to `vibe --agent` and ignores `profile`.

That creates the semantic bug:

- for Codex, `model` means model;
- for Vibe, `model` means profile/agent preset.

It also means the global config model says one thing while one backend does another.

## Recommended Decision

Use these semantics consistently:

- `backend`: adapter family to use, such as `codex` or `vibe`
- `profile`: named backend preset, profile, or agent persona that can package model choice plus other runtime behavior
- `model`: the underlying LLM to use when the backend exposes direct model selection
- `path`: working directory override at execution time

This keeps the user-facing surface small and fixes the meaning mismatch without introducing a new config key.

## Backend Mapping Rules

### Codex

- `profile` -> Codex profile resolution / `--profile`
- `model` -> `--model`
- `path` -> `--cd`

### Vibe

- `profile` -> `--agent`
- `path` -> `--workdir`
- `model` -> invalid for Vibe and should fail validation

This matches the user intent that Vibe's `--agent` behaves more like a profile selector than a raw model selector.

Recommended testing convention:

- use a dedicated Vibe test profile such as `testagent` for integration tests;
- configure that profile in the local Vibe setup to point at a smaller, cheaper model;
- select it through `profile`, not `model`.

This keeps test configuration aligned with the shared semantics while reducing cost and latency for backend-backed integration coverage.

## Validation Rule

Apply the corrected semantics directly.

Recommended behavior:

1. Vibe uses `profile` for `--agent`.
2. Vibe rejects `model`.
3. If both `profile` and `model` are supplied for Vibe, fail clearly.

This keeps the contract strict and prevents the incorrect meaning from persisting in code or config.

## Proposed Code Changes

### 1. Clarify Shared Settings Semantics

Update:

- `src/developer/agents/settings.py`
- `src/developer/agents/protocol.py`

Changes:

- rewrite field descriptions and constructor docstrings so `profile` is the generic preset/profile field;
- document that `profile` may include more than model selection, such as tools, prompts, and permissions;
- document that `model` refers to the underlying LLM, not a backend-specific preset;
- keep `path` as the execution-directory input.

This is the contract change that everything else should follow.

### 2. Normalize Selection Before Adapter Construction

Update:

- `src/developer/agents/select_agent_service.py`

Recommended behavior:

- keep config lookup as it is today;
- add one backend-aware normalization step before adapter creation;
- raise clear validation errors for impossible combinations.

Suggested normalization rules:

- `codex`: pass through `profile`, `model`, `path`
- `vibe`: map `profile` to adapter profile, pass `path`, and fail if `model` is provided

This keeps backend-specific interpretation out of the higher-level call sites.

### 3. Fix Vibe Adapter Semantics

Update:

- `src/developer/agents/adapters/vibe_adapter.py`

Changes:

- build `vibe --agent` from `self.profile`, not `self.model`;
- keep `self.path` mapped to `--workdir`;
- fail with an actionable error message when `model` is provided;
- update docstrings so the adapter makes the distinction explicit.

This is the actual bug fix.

### 4. Keep Codex Behavior As-Is

Update only docs or comments if needed in:

- `src/developer/agents/adapters/codex_adapter.py`

Codex already matches the desired semantics:

- profile-like config goes through profile resolution;
- model-like config goes through `--model`.

The main change here is to ensure naming and tests reflect that this is now the shared contract, not just Codex-specific behavior.

### 5. Fix Per-Check Override Semantics

Update:

- `src/developer/quality/adapters/agentic_review_adapter.py`

Changes:

- keep check-level `profile`, `model`, `backend`, and `path` fields;
- rely on the normalized selection flow so check overrides follow the same rules as global config;
- update field descriptions so Vibe users know to use `profile` for agent selection.

This ensures `[quality]`-driven or per-check overrides do the correct thing too.

## Tests To Update

### Config and Selection

Update:

- `tests/config/test_domain_settings.py`
- `tests/config/test_select_agent_service.py`

Update existing coverage to reflect:

- `profile` and `model` default semantics;
- Vibe selection using `profile` as the effective `--agent` source;
- clear failure when Vibe is given `model`;
- clear failure when both Vibe `profile` and `model` are given.

### Vibe Adapter

Update:

- `tests/agents/adapters/test_vibe_adapter.py`

Update existing coverage to reflect:

- `VibeAdapter(profile="testagent")` as the preferred integration-test setup;
- `model` no longer being used as the `--agent` source;
- failure path when `model` is provided;
- path handling remaining unchanged.

### Codex Adapter

Update if needed:

- `tests/agents/adapters/test_codex_adapter.py`

Keep or add assertions proving:

- `model` still maps to `--model`;
- `profile` still maps to profile resolution.

### Quality Adapter

Update if needed:

- `tests/quality/adapters/test_agentic_review_adapter.py`

Update existing assertions so per-check overrides are forwarded with the corrected semantics.

## Config And Fixture Updates

Update sample or fixture configs to follow the corrected meaning.

Likely files:

- `engineeringagent.toml`
- `tests/presentation/stub_data/implementation_run/engineeringagent.toml`

Update rule:

- if the backend is `vibe` and the value names an agent/profile like `devstral-small`, move it from `model` to `profile`.

Recommended test fixture convention:

- use `profile = "testagent"` for Vibe integration coverage in test fixtures and local test config.

## Contributor Documentation Follow-Up

Add a contributor-facing backend doc under `docs/contributor/` so the semantics are explicit outside the code.

Recommended addition:

- `docs/contributor/AGENT_BACKENDS.md`

Recommended contents:

- what `backend`, `profile`, `model`, and `path` mean across the system;
- that `profile` is broader than `model` and may include tools, prompts, and permissions in addition to model choice;
- how those shared fields map to each backend CLI;
- Codex examples showing `profile` and `model` together;
- Vibe examples showing that `profile` maps to `--agent`;
- guidance for tests and fixtures so new coverage uses the corrected semantics.

This doc should be added in the same implementation stream as the code fix, so contributors do not keep reintroducing the old meaning.

## Naming Follow-Up

The current `developer.agents` package name collides conceptually with orchestration terms like `ImplementationAgent`.

The concrete adapters in that package are closer to backend integrations than to workflow agents.

Chosen rename:

- `developer.agent_backends`

Why this is the best fit:

- it distinguishes backend integrations from orchestration agents;
- it stays close to the current domain language of `backend` in config;
- it makes `codex` and `vibe` read naturally as backend implementations; and
- it leaves room for selection, settings, and protocol modules without sounding like workflow code.

Recommended scope for the rename:

- rename `src/developer/agents/` to `src/developer/agent_backends/`
- update imports across `src/` and `tests/`
- rename references in config and contributor docs only when they mention Python module paths
- keep user-facing config keys like `[agents]` unchanged unless there is a separate reason to rename the config surface too

Recommended module mapping:

- `developer.agents.protocol` -> `developer.agent_backends.protocol`
- `developer.agents.settings` -> `developer.agent_backends.settings`
- `developer.agents.select_agent_service` -> `developer.agent_backends.select_agent_service`
- `developer.agents.adapters.codex_adapter` -> `developer.agent_backends.adapters.codex_adapter`
- `developer.agents.adapters.vibe_adapter` -> `developer.agent_backends.adapters.vibe_adapter`

Recommended symbol renames for consistency:

- `SelectAgentService` -> `SelectAgentBackendService`
- `get_agent_service()` -> `get_agent_backend_service()`
- `AgentProtocol` -> `AgentBackendProtocol`
- `AgentSettings` -> `AgentBackendSettings`
- private helper protocol `_AgentSelectionService` -> `_AgentBackendSelectionService`

Rationale:

- after renaming the package, `select_agent_service` still sounds like it selects orchestration agents;
- the service actually selects backend integrations such as Codex or Vibe; and
- `AgentProtocol` is also too easy to confuse with workflow-level agents;
- `AgentSettings` reads like configuration for orchestration behavior rather than backend selection; and
- the longer names are a little heavier, but they are much less ambiguous beside `ImplementationAgent`.

If a slightly cleaner name is preferred, this is the best alternate:

- module: `backend_selection_service.py`
- class: `BackendSelectionService`

Recommended default:

- keep the current verb-first style and use `select_agent_backend_service.py` with `SelectAgentBackendService`

That keeps the rename mechanically close to the current code while still fixing the ambiguity.

Additional recommendation:

- keep backend-specific class names like `CodexAdapter` and `VibeAdapter` as they are

Why keep those names:

- they are already clearly backend-oriented;
- adding `Backend` to every concrete adapter name would be redundant inside `developer.agent_backends`; and
- the ambiguity problem is mainly with shared abstractions, not with concrete backend classes.

Recommended file and symbol mapping:

- `developer.agents.protocol.AgentProtocol` -> `developer.agent_backends.protocol.AgentBackendProtocol`
- `developer.agents.settings.AgentSettings` -> `developer.agent_backends.settings.AgentBackendSettings`
- `developer.agents.select_agent_service.SelectAgentService` -> `developer.agent_backends.select_agent_backend_service.SelectAgentBackendService`
- `developer.agents.select_agent_service.get_agent_service` -> `developer.agent_backends.select_agent_backend_service.get_agent_backend_service`

Likely dependent rename sites:

- `src/developer/application/workspace_bridges.py`
- `src/developer/quality/adapters/agentic_review_adapter.py`
- `src/developer/orchestrators/protocols.py` only where backend protocol imports are referenced
- all tests that import shared backend-selection types

Names that should stay unchanged:

- config section `[agents]`
- config field `backend`
- backend-specific adapters `CodexAdapter` and `VibeAdapter`
- orchestrator-facing `ImplementationAgent`

This keeps the rename focused on the ambiguous shared abstractions rather than churning every identifier in the system.

Recommended implementation order for the rename:

1. move the package and update internal imports
2. update external imports in `src/` and `tests/`
3. update contributor docs to use `developer.agent_backends`
4. run the full test suite

Recommended default execution strategy:

- do the package rename in the same implementation stream as the semantics fix only if the resulting diff remains easy to review
- otherwise land the semantics fix first and the package rename immediately after

## Implementation Order

### Phase 1: Contract Cleanup

- update settings and protocol docs to define the intended meanings clearly
- add normalization rules in selection service

### Phase 2: Backend Fix

- switch Vibe adapter to use `profile` for `--agent`
- reject invalid Vibe `model` usage

### Phase 3: Test Migration

- update config and adapter tests
- update existing assertions for strict validation and conflict handling

### Phase 4: Fixture And Config Migration

- update repo config samples and test fixtures to use `profile` for Vibe presets

### Phase 5: Contributor Docs

- add `docs/contributor/AGENT_BACKENDS.md`
- document backend mapping rules

### Phase 6: Cleanup

- keep the shared semantics stable after that point

## Recommended Default Behavior

Unless there is a strong reason to redesign the entire selection API, the least disruptive fix is:

- keep the existing `profile` and `model` fields;
- redefine `profile` as the backend-agnostic preset/profile field;
- redefine `model` as a raw model override only;
- use `profile` for Vibe `--agent`;
- fail on unsupported Vibe `model` usage.

That fixes the bug, preserves the simple config surface, and avoids turning backend-specific flag names into shared configuration semantics.
