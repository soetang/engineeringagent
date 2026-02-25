# Agent Backends Architecture (To-Be)

## Purpose

Define a backend architecture where all agent invocations go through one run path and backend-specific details stay behind a registry boundary.

## Non-goals

- Document current implementation tradeoffs.
- Define migration steps.
- Split structured-output execution into a separate public call surface.

## Core Outcome

There is one canonical invocation flow for agents. Structured output is selected via
`output_type`, while backend-specific structured execution behavior remains owned by
the backend implementation.

## Public API

`run_agent(project_root, prompt, *, output_type=str, ...) -> str | ParsedObject`

Behavior:

- `output_type is str`: text response mode.
- `output_type is not str`: structured-output mode using the same backend selection and run boundary.
- Return semantics stay stable: text mode returns `str`; structured mode returns the
  parsed validated object.
- Same error taxonomy and telemetry fields in both modes.

## Architectural Rule: Single Run Path

Do not create separate public API entrypoints for structured output.

Specifically:

- No separate top-level `run_structured_agent(...)` API.
- No backend-specific duplication of text-vs-structured dispatch logic in loop/runtime call sites.

Structured output is handled through the same `run_agent(...)` orchestration boundary,
with backend strategy details encapsulated behind the agents package.

## Contracts

### BackendRegistry

Owns backend discovery and deterministic backend selection from configuration.

### AgentBackend

Single backend contract for raw invocation. Backends return raw text plus metadata.
Backends may additionally implement structured execution capabilities while staying
behind the same `run_agent(...)` boundary.

### AgentRunRequest

One request model containing:

- `project_root`
- `prompt`
- `backend_id` (resolved, optional override)
- `output_type` (`str` for text, schema type for structured)
- retry/session options

### AgentRunResult

Public return values are mode-specific:

- text mode: `str`
- structured mode: parsed object matching `output_type`

## Structured Output in the Same Flow

When `output_type` is not `str`, `run_agent` performs:

1. Same backend resolution as text mode.
2. Same backend invocation method.
3. Backend-owned structured strategy (including schema transport and retry policy).
4. Parsed object returned when validation succeeds.

This keeps the call boundary unified while allowing backend-specific structured
behavior differences (for example, prompt-retry vs native schema mode) to remain
localized under backend implementations.

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
- Backend-owned structured retry/validation policy.
- Backend concerns remain isolated from loop orchestration.
