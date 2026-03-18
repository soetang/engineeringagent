# Plan: Move Agent Path to Constructor and Wire Orchestrator Through Agents Module

## Goal
Align the agents contract so that execution context (`path`) is configured during agent construction, keep orchestrator format-driven (`output_format`) and maintain existing quality behavior with per-check agent instantiation.

## Current State (as-is)
- `AgentProtocol.run_agent` takes `path` as a per-call argument.
- `CodexAdapter` and `VibeAdapter` pass `path` through to their CLI command builders during each run.
- `AgentOrchestrator` currently calls an `AgentRunner` and expects to pass `AgentResult` as `output_format`.
- `AgenticReviewAdapter` currently creates/uses one agent instance and passes `check.path` on each `run_agent` call.

## Target State
- `AgentProtocol` keeps `run_agent(prompt, output_format=None)` without `path` argument.
- `path` is set in `__init__` of agent implementations and stored as immutable execution context for the agent instance.
- `SelectAgentService` accepts optional `path` and passes it to the selected adapter constructor.
- `AgenticReviewAdapter` instantiates a path-bound agent per check when `check.path` is present or relevant.
- Orchestrator uses the same agent protocol and remains fully format-driven by passing `output_format=AgentResult`.

### Contract relationship (must be followed)
- Think of two related interfaces:
  - **Agent construction contract**: `AgentProtocol`.
    - Includes adapter construction (`__init__`) with config-like inputs (`profile`, `model`, `path`).
    - Represents a configurable agent that can be selected via `SelectAgentService`.
  - **Agent execution contract**: `AgentRunner` (orchestrator protocol).
    - Includes `run_agent(prompt, output_format=None)` only.
    - Represents how the orchestrator consumes an already-configured agent.
- Rule: orchestrator code must only rely on execution contract semantics and must never know about adapter construction args.
- Rule: selection/creation code (e.g. `SelectAgentService`, per-check quality overrides) owns all construction args, including `path`.
- Interpretation: `AgentProtocol` is a superset of the execution contract; all agents are both constructors+executors, while orchestrator depends only on execution behavior.

## Why this direction
- Better separation: execution context is part of agent configuration, not command-time data.
- Supports your expectation that orchestrator can run in a different path by selecting agent with a dedicated path.
- Compatible with existing check-level overrides in quality because quality already reasons per check.

## Work Plan

### 1) Update `AgentProtocol` contract
File: `src/developer/agents/protocol.py`

- Change constructor signature to:
  - `__init__(profile: Optional[str] = None, model: Optional[str] = None, path: Optional[str] = None)`
- Change `run_agent` signature to:
  - `run_agent(self, prompt: str, output_format: Optional[Type[TModel]] = None) -> TModel | str`
- Keep behavior and return type semantics unchanged.

### 2) Update agent implementations to use constructor path
Files:
- `src/developer/agents/adapters/codex_adapter.py`
- `src/developer/agents/adapters/vibe_adapter.py`

For each adapter:
- Extend `__init__` to store `self.path = path`.
- Remove `path` parameter from internal and public run method signatures.
- Update command builder calls to use `self.path` instead of method argument.
- Ensure no behavioral regression for path-omitted calls (`path` remains optional).

### 3) Update agent selection wiring
File: `src/developer/agents/select_agent_service.py`

- Extend `select_agent(...)` to accept optional `path` and forward into constructor.
- Keep config/override semantics unchanged:
  - Missing values still come from config.
  - Explicit args still override config.
- Ensure return types remain `AgentProtocol`.

### 4) Update orchestrator protocol/callsite to match format-driven agent protocol
Files:
- `src/developer/orchestrator/protocols.py`
- `src/developer/orchestrator/orchestrator.py`

- In orchestrator protocol, require `run_agent(prompt, output_format=...) -> BaseModel | str`.
- Update callsite to use `run_agent` (not a new wrapper method).
- Keep orchestrator loop logic unchanged; continue to pass `output_format=AgentResult`.

### 5) Update quality adapter to instantiate per-check path-bound agent
File: `src/developer/quality/adapters/agentic_review_adapter.py`

- In `run_check`, construct/check for-check overrides inline when `backend/profile/model/path` is present, otherwise use pre-built adapter-level agent.
- If no check-specific backend is provided, use the service-selected default agent as configured by check/service defaults.
- Verify behavior for mixed `path`/`backend`/`profile`/`model` combinations.

### 5a) Add guardrails against future confusion (documentation only)
- In code reviews, verify adapter consumers use the correct abstraction:
  - `SelectAgentService`/quality path-aware callers should pass constructor args (`path`, `backend`, `profile`, `model`).
  - Orchestrator-like callers should call only `run_agent(prompt, output_format=...)`.
- When touching types, keep the two names (`AgentProtocol` and `AgentRunner`) in documentation/comments where ambiguity is possible.
- If this grows, consider renaming `AgentRunner` to `AgentExecutor` for semantic clarity.

### 6) Update local fakes/mocks in tests for new signature
Files:
- `tests/quality/adapters/test_agentic_review_adapter.py`
- `tests/quality/adapters/test_agentic_review_adapter_mock.py`

Tasks:
- Update any mock `run_agent` implementations to remove `path` arg.
- If a mock stores context, accept/verify `path` through constructor.
- Ensure test doubles still satisfy protocol behavior.

### 7) Update orchestrator test helper for new protocol name/signature
File: `tests/orchestrator/test_orchestrator.py`

- Ensure fake runner uses `run_agent` matching orchestrator protocol.
- Keep current behavioral assertions; only signature alignment changes.

### 8) Validation and regression checks
Run tests in focused order:
1. `pytest tests/orchestrator/test_orchestrator.py -q`
2. `pytest tests/quality/adapters/test_agentic_review_adapter.py -q`
3. `pytest tests/quality/adapters/test_agentic_review_adapter_mock.py -q`
4. `pytest tests/agents/adapters/test_codex_adapter.py -q` (non-integration subset if possible)
5. `pytest tests/agents/adapters/test_vibe_adapter.py -q` (non-integration subset if possible)

Then run the full suite if green.

## Acceptance Criteria
- Orchestrator run still works by passing `output_format=AgentResult` and receives structured output.
- `check.path` behavior is preserved via per-check agent instantiation in quality.
- `path` is no longer passed per `run_agent` call anywhere in production code.
- No protocol mismatch between agents, orchestrator, and quality compile-time/static expectations.
- Existing tests pass after updates, or intentionally updated tests reflect new constructor-bound path behavior.

## Risks / Notes
- Any direct callsites outside this repo that still use old `run_agent(..., path=...)` will need migration.
- If tests expect `run_agent` to accept `path`, those mocks must be updated or made more permissive.
