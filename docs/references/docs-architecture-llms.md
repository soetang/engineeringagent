# Documentation Architecture for LLMs

This guide defines who each documentation surface is for, what belongs in it, and how agents should author updates.

## Audience Split

- Human-readable docs are for repository users who need fast context and a clear path to first success.
- Agent-only docs are for coding agents that need deterministic rules, constraints, and execution contracts.
- Do not mix audiences in one document unless the file is explicitly marked as a bridge.

## Human-Readable Documentation Principles

- Lead with user outcome before mechanics.
- Keep onboarding concise and approachable.
- Link to deeper references instead of embedding every operational detail.
- Use presentation choices that improve readability for people.

## Agent-Only Documentation Principles

- Keep content text-first, explicit, and deterministic.
- Prefer normative rules, ordered checklists, and validation commands.
- Define ownership of behavior in code, gates, and schemas when possible.
- Avoid decorative writing that does not improve execution quality.

## Ownership and Placement

- `README.md` is the primary human entrypoint.
- `AGENTS.md` is the primary agent routing map.
- `docs/references/*-llms.md` contains agent-focused operating references.
- Specs under `docs/spec/features/*.yaml` define loop-scoped execution work.

## Authoring Expectations for Agents

- When updating human docs, optimize for clarity and first-run success.
- When updating agent docs, optimize for unambiguous execution and verification.
- Keep changes minimal and scoped to the active feature subtask.
- Add or update links in `AGENTS.md` when new agent references are introduced.
- Keep `init` bootstrap guidance explicit in human docs: default `core` profile, optional `python_uv` via `--scaffold-profile`.
