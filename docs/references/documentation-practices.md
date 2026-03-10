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
- Point contributors to `uv run engineeringagent approach list` when they need discoverable workflow/reference topics.

## Ownership and Placement
- `engineeringagent approach` provides operational reference topics for users and contributors; discover them with `uv run engineeringagent approach list`.
- Feature packages rooted at `docs/spec/features/<feature>/spec.yaml` define loop-scoped execution work.
- Treat flat `docs/spec/features/*.yaml` files as temporary compatibility wrappers only; they must point to the canonical bundled package instead of becoming a second design source.
- Keep `spec.yaml` as the canonical feature contract and use bundled `plan.md` phases for implementation sequencing when the planning tier requires a plan artifact.
