# Reference

## Commands

### `engineeringagent init`

Interactive onboarding flow that scaffolds:

- `engineeringagent.toml`
- optional `AGENTS.md` guidance
- prompt templates under `<harness-dir>/prompts/`
- quality files under `<harness-dir>/`
- `docs/plans/example-plan.md`

Behavior notes:

- prompts for the harness directory name, default `harness`;
- prompts before changing `engineeringagent.toml`;
- prompts before creating or appending the `AGENTS.md` block;
- creates missing files and skips existing scaffold files; and
- preserves existing `AGENTS.md` content and avoids appending duplicate guidance.

### `engineeringagent schema plan`

Prints JSON Schema for markdown task-plan frontmatter to stdout.

Important rule:

- this schema applies only to the YAML frontmatter object between the leading `---` delimiters;
- it does not apply to the rest of the markdown file body.

The exported schema requires:

- `schema_version`
- `task_id`
- `title`
- `status`
- `phases`

Supported plan status values are `draft`, `ready`, `in_progress`, `done`, and `blocked`.

### `engineeringagent schema quality`

Prints JSON Schema for the supported quality YAML structure to stdout.

Use it for editor tooling, agent prompts, or external validation when producing files referenced from `<harness-dir>/checks.yaml`.

### `engineeringagent validate-plan <plan.md>`

Validates one markdown plan file. The command accepts the path with or without a leading `@`.

It checks the parsed frontmatter and fails with field-level errors when required fields are missing or malformed.

### `engineeringagent check validate`

Validates `checks.yaml` and referenced quality files before execution.

### `engineeringagent check run`

Executes configured quality checks. The optional `--phase` flag defaults to `IterationComplete`.

### `engineeringagent implement <plan.md>`

Starts an implementation run for one markdown plan. The optional `--max-iterations` flag accepts a positive integer or `infinite`.

## Config written by `init`

`engineeringagent init` writes these keys when they are missing:

```toml
[prompts]
implementation_prompt_path = "harness/prompts/implementation_prompt.md"
commit_prompt_path = "harness/prompts/commit_message_prompt.md"
pull_request_prompt_path = "harness/prompts/pull_request_prompt.md"

[quality]
checks_path = "harness/checks.yaml"

[implementation]
max_iterations = 40
```

If a key already exists, `init` keeps the existing value instead of replacing it.

## Generated AGENTS.md snippet

The generated block tells agents to:

- invoke commands through `engineeringagent ...`;
- use `init`, `schema`, `validate-plan`, `check`, and `implement`;
- look for generated harness files under the chosen harness directory;
- use the sample plan under `docs/plans/`; and
- prefer the generated schemas and templates over ad hoc formats.

The snippet is wrapped in `<!-- engineeringagent:init:start -->` and `<!-- engineeringagent:init:end -->` markers so repeated runs can detect and avoid duplicate inserts.

## Plan frontmatter rules

A valid markdown plan has YAML frontmatter at the top of the file. The frontmatter schema includes:

- `schema_version = 1`
- non-empty `task_id`
- non-empty `title`
- `status` from the supported status enum
- a non-empty `phases` array

Each phase needs:

- `id`
- `title`
- `status`

`branch` and `base_branch` are optional string fields.

The markdown body after the frontmatter is still important for humans and agents, but it is not covered by `engineeringagent schema plan`.

## Quality YAML structure

The scaffolded quality setup uses:

1. `<harness-dir>/checks.yaml` as the top-level list of referenced quality files.
2. `<harness-dir>/quality/*.yaml` files as concrete check definitions.

The starter `commands.yaml` file uses direct local tool commands that you can edit to match your environment.

## Common failures

- `engineeringagent.toml` already exists with custom paths: `init` keeps those values, so generated files may not match your custom paths unless you align them intentionally.
- A scaffold file already exists: `init` reports it as skipped instead of overwriting it.
- `AGENTS.md` already contains the `engineeringagent:init` block: `init` skips the duplicate append.
- `validate-plan` fails on a markdown file without YAML frontmatter: add the opening and closing `---` delimiters.
- `validate-plan` fails on a schema export example: use `schema plan` for frontmatter generation only, not as a schema for the full markdown document.
- `check validate` fails: confirm that `<harness-dir>/checks.yaml` points to real quality files and that those files match `engineeringagent schema quality`.
