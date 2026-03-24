# developer

`developer` is a CLI for agent-driven implementation loops with markdown task plans and repository-local quality checks.

Install the CLI however you prefer, then run `developer ...` commands.

Quickstart:

```bash
developer init
developer schema plan
developer validate-plan docs/plans/example-plan.md
developer check validate
developer implement docs/plans/example-plan.md
```

`developer init` scaffolds `engineeringagent.toml`, `AGENTS.md`, prompt templates, quality checks, and `docs/plans/example-plan.md`.

Schema export examples:

```bash
developer schema plan > plan-frontmatter.schema.json
developer schema quality > quality.schema.json
```

The plan schema describes only the YAML frontmatter at the top of a markdown plan file, not the full markdown document body.

See `docs/getting-started.md` and `docs/reference.md`.
