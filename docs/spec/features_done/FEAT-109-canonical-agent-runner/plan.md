---
plan_id: FEAT-109
feature_id: FEAT-109
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define canonical agent interface and typed exceptions
  status: done
  verification:
  - uv run python -c "import engineeringagent.agents as a; assert hasattr(a, 'run_agent');
    print('ok')"
  - uv run pytest -q
- id: ST-002
  title: Implement OpenCode backend and prompted-JSON strategy with internal retries
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Add unit tests for structured output validation and retry behavior
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Migrate all production callsites to use run_agent (remove start_agent usage)
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Add pytest guard preventing bypass of the agent boundary
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: Map agent backend failures to deterministic reviewer decisions
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Address reviewer feedback on test brittleness
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define canonical agent interface and typed exceptions

Create `engineeringagent.agents` module with: - public `run_agent` API returning only the output value - AgentBackend interface - exceptions for structured output failures Ensure typing supports `str` and TypeAdapter-supported schemas.

## ST-002 Implement OpenCode backend and prompted-JSON strategy with internal retries

Implement AgentBackend for OpenCode using `engineeringagent.opencode.client.start_agent` as the subprocess runner and session provider. Add prompted JSON schema injection, parsing, validation, and internal bounded same-session retries into `run_agent`.

## ST-003 Add unit tests for structured output validation and retry behavior

Add tests that stub/mock the backend to simulate: - invalid JSON then valid JSON (internal same-session retry) - valid JSON but schema mismatch then corrected output - retry exhaustion => typed exception with bounded details Ensure determinism of retry prompt templates and truncation behavior.

## ST-004 Migrate all production callsites to use run_agent (remove start_agent usage)

Refactor production code to depend on the canonical agent runner contract. This includes checks/loop/cli wiring and reviewers.
Goals: - No imports of `engineeringagent.opencode.client.start_agent` outside
  `engineeringagent/opencode/**` and `engineeringagent/agents/**`.
- No direct references to `format=\"json\"` outside `engineeringagent/agents/**`.

## ST-005 Add pytest guard preventing bypass of the agent boundary

Add deterministic regression tests preventing: - importing `engineeringagent.opencode.client.start_agent` outside allowed modules - passing OpenCode-specific structured-output flags (e.g. `format=\"json\"`) outside
  `engineeringagent/agents/**`

## ST-006 Map agent backend failures to deterministic reviewer decisions

Ensure reviewer execution wraps backend crashes (`AgentBackendError`) and returns a deterministic request_changes decision envelope instead of raising.

## ST-007 Address reviewer feedback on test brittleness

Remove brittle prompt-content and internal call count assertions; ensure test doubles treat numeric retry counts as ints and avoid introspection asserts that are not part of the public contract.
