# Engineering Agent

NOTE: This repository is under active development. You should probably not use it for
anything important yet. Treat `engineeringagent init` as experimental scaffolding and review all generated
changes before committing.

## What this is

The goal of Engineeringagent is to help you move from ideas to quality implementations. The core idea is setup a structure for harness for you coding agent (lint, checks, fitness functions, agentic reviewers etc). You have to decide your self which checks is nessesary for you - just write a spec for it and let the agent implement. When a bundled feature package is ready, implement it with engineeringagent. Each `uv run engineeringagent run --all` iteration selects one eligible feature and one eligible plan phase, or compatibility-wrapper subtask, clears context, and runs the requested checks and validations with feedback carried into the next pass.

See [Principles](src/engineeringagent/approach/docs/principles.md) for core ideas with engineeringagent

This means the flow is really simple:

**Primary flow:** `spec -> implement`

## Minimal onboarding

1. Run `uv run engineeringagent init` - this creates the necessary files and guides you through the first decisions.
2. Start your favorite coding agent at the repository root.
3. Ask it to write a bundled feature package rooted at `docs/specifications/features/FEAT-XXX-some-header/spec.yaml`.
4. Keep `spec.yaml` outcome-oriented and put implementation sequencing in `plan.md` phases when the feature uses a `planned` or `researched` planning tier.
5. Implement the spec with `uv run engineeringagent run --all`.

OBS: This will commit changes to your code!
Currently opencode and codex is supported. 

## AGENTS bootstrap fallback

If your repo does not want to fully edit AGENTS.md first, use this minimum bootstrap snippet in `AGENTS.md`:

```text
In this repository, run EngineeringAgent CLI commands with `uv run engineeringagent ...`.
Use `uv run engineeringagent approach` for the overall workflow and guidance map.
Use `uv run engineeringagent approach list` to discover topics, then open one (for example `uv run engineeringagent approach specifications`).
```

This is important as the CLI contains the instructions for the agent how to use the engineeringagent. So to make sure it is used correctly the agent needs to be aware of it. Else keep the AGENTS.md slim - make it a map with links to relevant documentation. Becarefull documenting the code in AGENTS.md - it might confuse the agent more than it helås. Never use a AGENTS.md, made by an agent. 

## Allowlist recommendation for restricted agents

If your repository uses restrictive agent command allowlists, add these commands:

- `uv run engineeringagent approach *`
- `uv run engineeringagent schema *`

## Repository hygiene

EngineeringAgent runtime state is written under `.engineeringagent/progress/` during real runs:
- `.engineeringagent/progress/runs/runs.jsonl`
- `.engineeringagent/progress/features/<FEATURE_ID>/run.txt`
- `.engineeringagent/progress/features/<FEATURE_ID>/handoff.md`
- `.engineeringagent/progress/reviewers/state.json`
This path is ignored by default via `/.engineeringagent/progress/` in `.gitignore`.
These artifacts are lazily materialized on first non-dry writes; dry-run loop execution does not create them.

## Contributor policy

- Pull requests are not accepted for this repository.
- Code changes are implemented through agents.
- Open issues for desired outcomes and constraints; useful issues can be promoted into specs.
