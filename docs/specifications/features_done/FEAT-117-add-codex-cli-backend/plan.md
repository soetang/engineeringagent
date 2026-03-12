---
plan_id: FEAT-117
feature_id: FEAT-117
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add codex backend package and client command runner
  status: done
  verification:
  - uv run pytest -q tests/agents
- id: ST-002
  title: Add CodexAgentBackend adapter implementing AgentBackend
  status: done
  verification:
  - uv run pytest -q tests/agents/test_codex_backend.py
- id: ST-003
  title: Add native structured-output capability contract in agents layer
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py
- id: ST-004
  title: Implement codex structured-output policy in codex backend strategy
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/agents/test_codex_backend.py
- id: ST-005
  title: Register codex backend in agents registry
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py::test_list_backends_returns_stable_sorted_tuple
- id: ST-006
  title: Add codex backend config resolvers
  status: done
  verification:
  - uv run pytest -q tests/config
- id: ST-007
  title: Add codex backend-owned scaffold templates for profiles
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-008
  title: Add codex backend unit tests for command wiring and errors
  status: done
  verification:
  - uv run pytest -q tests/agents/test_codex_backend.py
- id: ST-009
  title: Add run_agent integration tests for codex structured no-retry behavior
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py
- id: ST-010
  title: Update subprocess boundary allowlist for codex backend client
  status: done
  verification:
  - uv run python harness/fitness_functions/check_loop_subprocess_boundary.py
  - uv run pytest -q tests/fitness
- id: ST-011
  title: Add end-to-end backend selection test for codex (post FEAT-115)
  status: done
  verification:
  - uv run pytest -q tests/loop
- id: ST-012
  title: Document codex backend scope and non-goals in feature docs
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-013
  title: Introduce agents strategy resolver and migrate default selection out of run_agent
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/config
- id: ST-014
  title: Add tests proving run_agent is a thin delegator on default path
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py
- id: ST-015
  title: Migrate this repository default backend to codex
  status: done
  verification:
  - uv run pytest -q tests/config tests/agents tests/loop
  - uv run pytest -q
- id: ST-016
  title: Remove and forbid reviewer $responseformat token
  status: done
  verification:
  - uv run pytest -q tests/reviewers tests/meta/test_validator.py
- id: ST-017
  title: Remove reviewer response-format injection and rely on structured output
  status: done
  verification:
  - uv run pytest -q tests/reviewers tests/harness/test_checks_runtime.py
  - uv run pytest -q tests/meta/test_validator.py tests/reviewers/test_repo_reviewers_config.py
- id: ST-018
  title: Migrate OpenCode structured-output handling into OpenCode backend strategy
  status: done
  verification:
  - uv run pytest -q tests/agents/test_opencode_backend.py tests/agents/test_agents_api.py
- id: ST-019
  title: Add consumer-agnostic structured-output contract tests
  status: done
  verification:
  - uv run pytest -q tests/agents/test_agents_api.py tests/reviewers
- id: ST-020
  title: Add structured JSON output format regression tests for reviewer envelopes
  status: done
  verification:
  - uv run pytest -q tests/reviewers tests/agents/test_agents_api.py
- id: ST-021
  title: Add codex output-schema integration unit tests (mocked subprocess)
  status: done
  verification:
  - uv run pytest -q tests/agents/test_codex_backend.py
- id: ST-022
  title: Archive completed FEAT-117 spec under features_done
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add codex backend package and client command runner

Implement codex client command construction and subprocess invocation in
`src/engineeringagent/agents/backends/codex/client.py`, including text and
structured modes.

Notes:
- Reopened for reviewer feedback and deduplicated Codex model-id normalization into shared codex.model_ids helper used by runtime and scaffold paths.
- Addressed code_simplifier feedback by extracting codex client process-args normalization and removing a redundant codex structured-output fallback.

Attempts: 3

## ST-002 Add CodexAgentBackend adapter implementing AgentBackend

Normalize client results into `AgentBackendRunResult` and map failures into
`AgentBackendError` with process metadata.

## ST-003 Add native structured-output capability contract in agents layer

Extend agents runtime contracts so each backend strategy owns structured-output
behavior. Codex uses native schema mode; OpenCode uses backend-owned prompt/
retry policy.

Keep run_agent as a thin delegator over strategy-owned structured handling.

## ST-004 Implement codex structured-output policy in codex backend strategy

Precondition: ST-013 and ST-014 are complete.

In structured mode, codex backend should use `--output-schema` and skip
retry loops while keeping one local validation guard.

Do not add codex-specific structured logic to run_agent.

Notes:
- Reopened for reviewer feedback and simplified codex schema traversal to recurse through all dict/list values instead of a key whitelist.
- Addressed code_simplifier follow-up by inlining object-property required normalization into the schema walker and simplifying Codex model-flag handling with unchanged semantics.

Attempts: 3

## ST-005 Register codex backend in agents registry

Add codex backend factory to the registry and keep tuple ordering stable.

## ST-006 Add codex backend config resolvers

Add resolvers for `[agents.codex]` and `[tool.engineeringagent.agents.codex]`
keys (`profile`, `model`) with deterministic precedence and validation.

## ST-007 Add codex backend-owned scaffold templates for profiles

Add backend-owned codex scaffold assets and init wiring to generate
`.codex/config.toml` when backend=codex is selected.

Do not scaffold multi-agent roles in this feature.

## ST-008 Add codex backend unit tests for command wiring and errors

Add tests for:
- text mode command args
- structured mode command args (`--output-schema` + `--output-last-message <path>`)
- missing executable mapping
- non-zero exit mapping

Notes:
- Reopened for reviewer feedback and refactored subprocess stubs via a shared output helper, plus added traversal regression coverage for nested non-whitelisted schema keys.
- Added branch-coverage regression for zero-length truncation limits and simplified monkeypatch targets to patch imported backend modules directly.

Attempts: 3

## ST-009 Add run_agent integration tests for codex structured no-retry behavior

Add tests that verify exactly one codex invocation in structured mode and
deterministic validation error surfacing without retry loops.

## ST-010 Update subprocess boundary allowlist for codex backend client

Update semgrep allowlist to permit subprocess calls in codex backend client
module and keep disallow policy elsewhere.

## ST-011 Add end-to-end backend selection test for codex (post FEAT-115)

After core loop backend-agnostic wiring lands, add a loop-level test where
`[agents] backend = "codex"` selects codex through the canonical boundary.

## ST-012 Document codex backend scope and non-goals in feature docs

Documented explicit scope/non-goal boundaries in this feature contract:
codex profile-based `.codex/config.toml` scaffolding is in scope; codex multi-agent
role scaffolding remains deferred/out of scope for v1.

## ST-013 Introduce agents strategy resolver and migrate default selection out of run_agent

Add an agents-layer runtime/strategy resolver that owns backend resolution from
TOML and backend construction. Migrate any FEAT-113 default selection logic that
currently lives in run_agent into this resolver.

## ST-014 Add tests proving run_agent is a thin delegator on default path

Add tests that monkeypatch the strategy resolver and assert run_agent default
behavior delegates to it for both text and structured output paths.

Notes:
- Addressed code_simplifier feedback by deduplicating configured-backend test doubles into shared helpers.

Attempts: 2

## ST-015 Migrate this repository default backend to codex

Precondition: FEAT-115 is complete.

Dogfood the new backend by migrating this repository's default backend to codex.

Required outcomes:
- Update repository configuration so default backend resolution returns codex
  for this repo (`engineeringagent.toml` [agents] backend = "codex").
- Add or update backend-specific repo config for codex (for example,
  profile/model under [agents.codex]) as needed by the codex backend runtime.
- Update tests/fixtures that implicitly assume opencode is the repository
  default backend.
- Add at least one deterministic test asserting repository default backend
  resolution is codex for this repo.
- Ensure migration tests are machine-independent: no test should require an
  installed/authenticated codex binary on the host by default (mock backend
  process invocation in unit tests).

Rollback plan:
- Revert repository default backend to previous value in engineeringagent.toml.
- Re-run tests/config + tests/agents + tests/loop to confirm deterministic
  behavior after rollback.

## ST-016 Remove and forbid reviewer $responseformat token

Update reviewer validation/runtime contracts so `$responseformat` is not supported.

Required outcomes:
- remove any runtime substitution/injection behavior for `$responseformat`
- remove any requirement that reviewer prompts contain `$responseformat`
- fail validation deterministically when `$responseformat` appears in any
  configured reviewer prompt file
- migrate in-repo reviewer prompts to remove the token

## ST-017 Remove reviewer response-format injection and rely on structured output

Remove any reviewer-specific output-contract injection text/logic.

Reviewer structured output formatting must be enforced by the generic
structured-output mechanism (backend strategy schema handling), not by
reviewer prompt token injection.

Update reviewer prompt docs and tests accordingly.

## ST-018 Migrate OpenCode structured-output handling into OpenCode backend strategy

Move OpenCode structured-output prompt wrapper/retry behavior from run_agent
into OpenCode backend strategy so structured-output ownership is consistent
across backends.

Required outcomes:
- OpenCode structured-output tests stay green with equivalent deterministic
  retry behavior.
- run_agent remains strategy-delegation only for structured flows.

## ST-019 Add consumer-agnostic structured-output contract tests

Add tests proving structured-output behavior is not tied to reviewers.

Required outcomes:
- Add at least one non-reviewer structured-output test path through run_agent
  for each backend strategy (using test doubles where needed).
- Assert no reviewer-specific prompt contract assumptions are required by the
  generic structured-output API.

## ST-020 Add structured JSON output format regression tests for reviewer envelopes

Add tests that pin the expected JSON output characteristics for reviewer
structured responses:
- output is a single strict JSON object (no code fences, no surrounding text)
- schema validation failures surface as `AgentOutputValidationError` with
  bounded details

Ensure tests cover at least one failure-mode payload (for example: code fences)
and one success payload.

## ST-021 Add codex output-schema integration unit tests (mocked subprocess)

Add tests for the codex backend client/strategy that prove:
- structured mode always uses `--output-schema` + `--output-last-message`
- the backend reads output-last-message (not stdout) as canonical
- schema constraints (enum/additionalProperties) are enforced end-to-end by
  validating the parsed JSON against the requested schema type

These tests must not require a real codex binary on the host; mock subprocess
execution and write a synthetic output-last-message file.

Notes:
- Replaced helper-coupled schema tests with public `run_structured` contract tests that assert emitted `config.output_schema` through the `run_codex_exec` boundary, including nested required fields in `$defs`, list-item objects, and nonstandard nested schema keys.
- Hardened schema-contract assertions to avoid coupling to pydantic-generated `$defs` key names while still verifying nested object `properties`/`required` alignment.

## ST-022 Archive completed FEAT-117 spec under features_done

Once retry feedback and final gates are fully resolved, move this feature spec from
`docs/spec/features/` to `docs/spec/features_done/` as the closeout step.

Notes:
- Reopened after reviewer-requested follow-up changes; keep in docs/spec/features until final closeout.
- Retry feedback resolved after fixing malformed active feature YAML parsing blockers and restoring green final gates.
- Reopened for this cycle while reviewer-requested follow-up changes are being validated before final archive.
- Applied reviewer-requested test hardening updates removing private-helper/constant monkeypatch coupling and validated stable public behavior coverage for Codex structured output.
- Reopened from test-review feedback and removed implementation-coupled prompt/config assertions and retained behavior-level structured-output checks.

Attempts: 4
