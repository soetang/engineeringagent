# Documentation Architecture Reference

This guide defines who each documentation surface is for, what belongs in it, and how contributors should author updates.

## Audience Split

- User docs are for operators adopting `engineeringagent` in their repositories.
- Contributor docs are for people maintaining the `engineeringagent` package itself.
- Keep audience and ownership explicit so scaffolding and policy checks stay deterministic.

## User Documentation Principles

- `README.md` is the primary user entrypoint.
- Lead with user outcome before mechanics.
- Keep onboarding concise and approachable.
- Link to deeper references instead of embedding every operational detail.
- Use presentation choices that improve readability for people.
- User docs are generally expected to be part of the scafold for `uv run engineeringagent init`

## Contributor Documentation Principles
- `AGENTS.md` is the primary contributor routing map.
- For in-repo loop command surfaces, document source-first execution forms (`uv run ...`)

## Ownership and Placement
- `docs/references/*.md` contains operational references for users and contributors.
- Specs under `docs/spec/features/*.yaml` define loop-scoped execution work.
