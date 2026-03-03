# AGENTS.md

In this repository, run EngineeringAgent CLI commands with `uvx engineeringagent ...`.

Use `engineeringagent approach` for the overall workflow and guidance map.

Use `engineeringagent approach list` to discover topics, then open one (for example `engineeringagent approach specifications`).

You can assume that this repository currently have no users. So changes are allowed to be breaking, and we prefer to improve the design and structure over maintaining exact compatbility with current functionality.

To access up-to-date guidance, use the CLI approach surface:
1. `engineeringagent approach` - Guidance map and topic overview.
1. `engineeringagent approach principles` - High-level engineering principles.
1. `engineeringagent approach workflow` - Workflow and execution sequence.
1. `engineeringagent approach specifications` - How to write and maintain specs.
1. `engineeringagent approach quality-checks` - Quality and verification playbook.
1. `engineeringagent approach reviewer-authoring` - Reviewer workflows and prompts.
1. [Architecture map](docs/architecture/Architecture.md) - Entry point for target-state architecture documents.

## Verification Quick Reference

- Validate specs: `uv run engineeringagent validate --schema-only`
- Inspect init profile options: `uv run engineeringagent init --help`
- Run iteration-end checks: `uv run engineeringagent checks run --phase iteration_end`
- Run feature-done checks: `uv run engineeringagent checks run --phase feature_done`
