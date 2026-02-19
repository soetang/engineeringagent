# Documentation Architecture Reference

This guide defines who each documentation surface is for, what belongs in it, and how contributors should author updates.

## Audience Split

- User docs are for operators adopting `engineeringagent` in their repositories.
- Contributor docs are for people maintaining the `engineeringagent` package itself.
- Keep audience and ownership explicit so scaffolding and policy checks stay deterministic.

## User Documentation Principles

- Lead with user outcome before mechanics.
- Keep onboarding concise and approachable.
- Link to deeper references instead of embedding every operational detail.
- Use presentation choices that improve readability for people.

## Contributor Documentation Principles

- Keep content text-first, explicit, and deterministic.
- Prefer normative rules, ordered checklists, and validation commands.
- Define ownership of behavior in code, gates, and schemas when possible.
- Treat API/contract change documentation as high priority, not optional context.
- Require explicit contract deltas in agent docs/specs: old behavior, new behavior, compatibility policy, and migration scope.
- Avoid decorative writing that does not improve execution quality.
- For in-repo loop command surfaces, document source-first execution forms (`uv run ...`) and avoid `uvx --from . engineeringagent ...`.

## In-Repo Loop Command Policy

- Scope policy guidance to loop-executed command surfaces: feature verification commands under `docs/spec/features/*.yaml` and command checks in `harness/checks.yaml`.
- Treat `uvx --from . engineeringagent ...` as forbidden for in-repo loop execution because it can execute cached package artifacts instead of workspace source.
- Provide actionable remediation with direct replacement intent, preferring `uv run engineeringagent ...`.

## Ownership and Placement

- `README.md` is the primary user entrypoint.
- `AGENTS.md` is the primary contributor routing map.
- `docs/references/*.md` contains operational references for users and contributors.
- Specs under `docs/spec/features/*.yaml` define loop-scoped execution work.

## Authoring Expectations for Agents

- When updating user docs, optimize for clarity and first-run success.
- When updating contributor docs, optimize for unambiguous execution and verification.
- If behavior contracts change, include explicit delta statements and verification evidence in the same documentation update.
- Keep changes minimal and scoped to the active feature subtask.
- Add or update links in `AGENTS.md` when new operational references are introduced.
- Keep `init` bootstrap guidance explicit in user docs: default `core` profile, optional `python_uv` via `--scaffold-profile`.
