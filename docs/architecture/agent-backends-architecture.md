# Agent Backends Architecture (To-Be)

## Purpose

Define a backend architecture where all agent invocations go through one run path and backend-specific details stay behind a registry boundary.

## Non-goals

- Document current implementation tradeoffs.
- Define migration steps.
- Split structured-output execution into a separate public call surface.

## Core Outcome

There is one canonical invocation flow for agents. Structured-output behavior is a mode of the same flow, not a separate backend surface.

## Public API

`run_agent(project_root, prompt, *, output_schema=None, ...) -> AgentRunResult`

Behavior:

- `output_schema is None`: text response mode.
- `output_schema is set`: structured-output mode using the same backend selection and run path.
- Same error taxonomy and telemetry fields in both modes.

## Architectural Rule: Single Run Path

Do not create separate backend interfaces/functions/methods for structured output.

Specifically:

- No separate backend strategy tree for structured output.
- No separate top-level `run_structured_agent(...)` API.
- No backend-specific duplication of text-vs-structured dispatch logic in loop/runtime call sites.

Structured output is handled by shared run-agent orchestration around the same backend invocation mechanism.

## Contracts

### BackendRegistry

Owns backend discovery and deterministic backend selection from configuration.

### AgentBackend

Single backend contract for raw invocation. Backends return raw text plus metadata.

### AgentRunRequest

One request model containing:

- `project_root`
- `prompt`
- `backend_id` (resolved, optional override)
- `output_schema` (optional)
- retry/session options

### AgentRunResult

One result model for both modes:

- `text` (raw backend text)
- `parsed` (optional validated structured object)
- `session_id` (optional)
- `backend`
- execution metadata

## Structured Output in the Same Flow

When `output_schema` is provided, `run_agent` performs:

1. Same backend resolution as text mode.
2. Same backend invocation method.
3. Shared validation/retry wrapper around returned text.
4. Parsed object stored in `parsed` when validation succeeds.

This keeps backend implementations focused on producing output, while schema-conformance policy lives in one place.

## Loop Boundary

Loop/runtime code must not branch on backend id and must not own structured-output retry logic.

Loop/runtime responsibilities are limited to:

- Supplying task prompt and optional schema.
- Handling success/failure from `run_agent`.

## Extensibility Rules

Adding a backend requires:

1. Implement single backend run contract.
2. Register backend factory.
3. Add backend-focused tests for invocation and error mapping.

No extra structured-output interface implementation is required.

## Invariants

- One canonical run-agent call path.
- Deterministic backend selection.
- Shared error taxonomy across text and structured modes.
- Shared retry and validation policy for structured mode.
- Backend concerns remain isolated from loop orchestration.
