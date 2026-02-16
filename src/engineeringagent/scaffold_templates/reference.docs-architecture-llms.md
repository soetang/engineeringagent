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
- Treat API/contract change documentation as high priority, not optional context.
- Require explicit contract deltas in agent docs/specs: old behavior, new behavior, compatibility policy, and migration scope.
- Avoid decorative writing that does not improve execution quality.
- For in-repo loop command surfaces, document source-first execution forms (`uv run ...`) and avoid `uvx --from . engineeringagent ...`.

## In-Repo Loop Command Policy

- Scope policy guidance to loop-executed command surfaces: feature verification commands under `docs/spec/features/*.yaml` and gate commands in `harness/gates.yaml`.
- Treat `uvx --from . engineeringagent ...` as forbidden for in-repo loop execution because it can execute cached package artifacts instead of workspace source.
- Provide actionable remediation with direct replacement intent, preferring `uv run python -m engineeringagent.cli ...`.

## Ownership and Placement

- `README.md` is the primary human entrypoint.
- `AGENTS.md` is the primary agent routing map.
- `docs/references/*-llms.md` contains agent-focused operating references.
- Specs under `docs/spec/features/*.yaml` define loop-scoped execution work.

## Authoring Expectations for Agents

- When updating human docs, optimize for clarity and first-run success.
- When updating agent docs, optimize for unambiguous execution and verification.
- If behavior contracts change, include explicit delta statements and verification evidence in the same documentation update.
- Keep changes minimal and scoped to the active feature subtask.
- Add or update links in `AGENTS.md` when new agent references are introduced.
- Keep `init` bootstrap guidance explicit in human docs: default `core` profile, optional `python_uv` via `--scaffold-profile`.
