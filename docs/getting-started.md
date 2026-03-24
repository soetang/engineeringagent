# Getting Started

This package is designed for repositories that want a small, agent-first workflow:

1. scaffold a local setup;
2. validate a markdown plan;
3. validate and run quality checks; and
4. launch the implementation loop.

## Bootstrap a repository

Run:

```bash
engineeringagent init
```

The command asks for:

- a harness directory name, defaulting to `harness`;
- whether to create or update `engineeringagent.toml`; and
- whether to create or append a package-specific `AGENTS.md` block.

The scaffolded layout is:

```text
engineeringagent.toml
AGENTS.md
<harness-dir>/checks.yaml
<harness-dir>/quality/commands.yaml
<harness-dir>/prompts/implementation_prompt.md
<harness-dir>/prompts/commit_message_prompt.md
<harness-dir>/prompts/pull_request_prompt.md
docs/plans/example-plan.md
```

What each file is for:

- `engineeringagent.toml`: points the CLI at the generated prompts and quality checks.
- `AGENTS.md`: optional repository-local guidance for code agents using this package.
- `<harness-dir>/checks.yaml`: top-level quality manifest.
- `<harness-dir>/quality/commands.yaml`: a minimal sample command check for `pytest`.
- `<harness-dir>/prompts/*.md`: starter prompts for implementation, commit messages, and pull requests.
- `docs/plans/example-plan.md`: a minimal markdown task plan that already matches the validator.

`engineeringagent init` does not silently overwrite scaffold files. Existing files are reported as skipped, and existing `AGENTS.md` content is preserved.

## Adopt the generated AGENTS.md guidance

If you opt in, `engineeringagent init` either creates `AGENTS.md` or appends a delimited `engineeringagent` block to the existing file. Re-running `init` does not duplicate that block.

The snippet is intentionally small. It tells agents to:

- run this package through `engineeringagent ...` commands;
- use `init`, `schema`, `validate-plan`, `check`, and `implement`;
- look in the scaffolded harness directory for prompts and checks; and
- reuse the generated schemas and templates instead of inventing new formats.

If your repository already has broader coding instructions, keep those and let the appended `engineeringagent` block cover only package-specific workflow.

## Generate schemas and validate a sample plan

Export machine-readable schemas with:

```bash
engineeringagent schema plan
engineeringagent schema quality
```

`engineeringagent schema plan` emits the schema for the YAML frontmatter object in a markdown plan file. It does not describe headings, task lists, or the rest of the markdown body.

Validate the generated sample plan with:

```bash
engineeringagent validate-plan docs/plans/example-plan.md
```

## Validate and run checks

First validate the quality configuration:

```bash
engineeringagent check validate
```

Then run the configured checks:

```bash
engineeringagent check run
```

The starter quality file runs:

- `pytest`

## Start an implementation run

Once the plan validates and checks are configured, start the implementation loop with:

```bash
engineeringagent implement docs/plans/example-plan.md
```

The default implementation prompt tells the agent to treat the markdown plan as the source of truth, update its checkboxes as work completes, validate plan status with `engineeringagent validate-plan`, and address prior feedback first when feedback is provided.
