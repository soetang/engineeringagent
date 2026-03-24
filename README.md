# engineeringagent

`engineeringagent` is a CLI for agent-driven implementation loops with markdown task plans and repository-local quality checks.

Install the CLI however you prefer, then run `engineeringagent ...` commands.

Quickstart:

```bash
engineeringagent init
engineeringagent schema plan
engineeringagent validate-plan docs/plans/example-plan.md
engineeringagent check validate
engineeringagent implement docs/plans/example-plan.md
```

`engineeringagent init` scaffolds `engineeringagent.toml`, `AGENTS.md`, prompt templates, quality checks, and `docs/plans/example-plan.md`.

Schema export examples:

```bash
engineeringagent schema plan > plan-frontmatter.schema.json
engineeringagent schema quality > quality.schema.json
```

The plan schema describes only the YAML frontmatter at the top of a markdown plan file, not the full markdown document body.

See `docs/getting-started.md` and `docs/reference.md`.
