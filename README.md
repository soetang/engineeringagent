# Engineering Agent

NOTE: This repository is under active development. You should probably not use it for
anything important yet. Treat `engineeringagent init` as experimental scaffolding and review all generated
changes before committing.

## What this is

Engineeringagent helps you move from ideas to implementations through specs.

**Primary flow:** `spec -> implement`

## Minimal onboarding

1. Start your favorite coding agent at the repository root.
2. Ask it to write a spec for your change in `docs/spec/features/<ID>.yaml`.
3. Run the spec with `uvx engineeringagent run <path-to-spec>`.

Prefer `--dry-run` for the first pass and review results before committing.

## AGENTS bootstrap fallback

If your repo does not want to fully edit AGENTS.md first, use this minimum bootstrap snippet in `AGENTS.md`:

```text
In this repository, run EngineeringAgent CLI commands with `uvx engineeringagent ...`.
Use `engineeringagent approach` for the overall workflow and guidance map.
Use `engineeringagent approach list` to discover topics, then open one (for example `engineeringagent approach specifications`).
```

## Allowlist recommendation for restricted agents

If your repository uses restrictive agent command allowlists, add these commands:

- `engineeringagent approach`
- `engineeringagent schema *`

## Contributor policy

- Pull requests are not accepted for this repository.
- Code changes are implemented through agents.
- Open issues for desired outcomes and constraints; useful issues can be promoted into specs.
