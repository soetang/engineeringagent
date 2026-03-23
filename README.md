# developer

`developer` is a CLI for agent-driven implementation loops with markdown task plans and repository-local quality checks.

Install dependencies with `uv sync`, then run commands as `uv run --active developer ...`.

Quickstart:

```bash
uv run --active developer init
uv run --active developer schema plan
uv run --active developer validate-plan docs/plans/example-plan.md
uv run --active developer check validate
uv run --active developer implement docs/plans/example-plan.md
```

`developer init` scaffolds `engineeringagent.toml`, `AGENTS.md`, prompt templates, quality checks, and `docs/plans/example-plan.md`.

Schema export examples:

```bash
uv run --active developer schema plan > plan-frontmatter.schema.json
uv run --active developer schema quality > quality.schema.json
```

The plan schema describes only the YAML frontmatter at the top of a markdown plan file, not the full markdown document body.

See [getting-started.md](/home/soetang/developer/developer-workspaces/be7caa66fba043de9e3be9daa7410cc8/docs/getting-started.md) and [reference.md](/home/soetang/developer/developer-workspaces/be7caa66fba043de9e3be9daa7410cc8/docs/reference.md).
