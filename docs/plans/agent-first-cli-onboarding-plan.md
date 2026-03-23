---
schema_version: 1
task_id: add-agent-first-cli-onboarding
title: Add minimal agent-first onboarding with init, schema export, and user docs
status: ready
branch: feat/add-agent-first-cli-onboarding
base_branch: main
phases:
  - id: cli
    title: Add minimal init and schema CLI commands
    status: todo
  - id: scaffolding
    title: Package and generate starter config, prompts, and templates
    status: todo
  - id: docs
    title: Document the minimal getting-started and reference flows
    status: todo
  - id: tests
    title: Cover onboarding CLI behavior and generated outputs
    status: todo
---

# Agent-First CLI Onboarding Plan

## Goal

Add a minimal, agent-friendly onboarding flow so new repositories can bootstrap `developer` quickly and generate valid plan and quality inputs without hand-discovering file formats.

After this change, users should be able to:

- run `developer init` to scaffold a small working setup;
- choose a harness folder name during setup;
- export machine-readable schemas for plan and quality inputs;
- follow a short `README.md` getting-started path; and
- find deeper details in a very small `docs/` set.

## Scope

Keep v1 intentionally small.

Include only:

- one interactive-first `developer init` command;
- one schema command group for plan and quality export;
- minimal generated files for config, prompts, checks, and a sample plan;
- `README.md`, `docs/getting-started.md`, and `docs/reference.md`; and
- targeted CLI and generation tests.

Do not include in this slice:

- a full documentation site framework;
- broad non-interactive automation flags beyond what is needed for testability;
- advanced scaffolds such as reviewers, fitness functions, or workspace presets by default; or
- schema export for every config section.

## Current State

- `README.md` is empty.
- There is no end-user onboarding command.
- Plan validation exists, but the plan shape is only implied by validator code.
- Quality validation exists, but the quality shape is only implied by dynamic Pydantic models and sample harness files.
- The repository already contains useful prompt and quality template material under `harness/`, but it is not packaged as a clean bootstrap flow.
- Prompt paths are not fully aligned today: `PromptSettings` defaults `implementation_prompt_path` to `harness/implementation_prompt.md` while the checked-in file lives at `harness/prompts/implementation_prompt.md`.

## Decision

Introduce a minimal onboarding flow centered on two command surfaces:

1. `developer init`
2. `developer schema <plan|quality>`

The documentation should follow that workflow:

1. initialize;
2. inspect generated files;
3. generate valid inputs from schema/template;
4. validate; and
5. run implementation/check commands.

## Command Design

### `developer init`

Add an interactive command that:

- asks for a harness directory name, defaulting to `harness`;
- asks whether to create or update `engineeringagent.toml`;
- writes prompt paths that match the generated scaffold layout;
- generates a minimal `checks.yaml` plus one referenced quality file; and
- generates one sample markdown plan template.

Recommended generated layout:

```text
engineeringagent.toml
<harness-dir>/checks.yaml
<harness-dir>/quality/commands.yaml
<harness-dir>/prompts/implementation_prompt.md
<harness-dir>/prompts/commit_message_prompt.md
<harness-dir>/prompts/pull_request_prompt.md
docs/plans/example-plan.md
```

Safety rules:

- never silently overwrite existing files;
- show a concise summary of created and skipped files; and
- keep the command useful even when only part of the scaffold is missing.

### `developer schema`

Add a small command group with:

- `developer schema plan`
- `developer schema quality`

Behavior:

- output JSON Schema to stdout by default;
- describe the markdown plan frontmatter object for `plan`;
- describe the supported quality YAML structure for `quality`; and
- keep the output stable enough for agents and editor tooling.

## Required Implementation Work

### Phase 1: CLI surface

- add `schema` command group to the root CLI;
- add `init` command to the root CLI;
- keep presentation code thin and push generation/schema logic into application-layer services where practical; and
- define the minimal prompt flow for interactive setup.

### Phase 2: Scaffold assets and generation

- create a canonical set of packaged starter templates;
- reuse existing harness prompt/check content where it fits the minimal bootstrap;
- normalize prompt path defaults to the generated directory structure; and
- implement file generation for config, prompts, checks, and example plan content.

### Phase 3: Schema export

- expose JSON Schema for the validated task-plan frontmatter shape;
- expose JSON Schema for the dynamic quality spec model;
- ensure schema output reflects supported enum values and required fields; and
- document clearly that the plan schema applies to frontmatter, not the whole markdown file.

### Phase 4: Documentation

- populate `README.md` with the shortest useful quickstart;
- add `docs/getting-started.md` for the bootstrap workflow; and
- add `docs/reference.md` for commands, config, schema rules, and common errors.

## Documentation Shape

Keep documentation limited to these files in v1:

- `README.md`
- `docs/getting-started.md`
- `docs/reference.md`

### `README.md`

Include only:

- project purpose;
- install/run basics;
- `developer init` quickstart;
- schema export examples; and
- links to the docs files.

### `docs/getting-started.md`

Cover:

- the agent-first bootstrap flow;
- generated files and what each one is for;
- validating a sample plan;
- validating and running checks; and
- starting an implementation run.

### `docs/reference.md`

Cover:

- command reference for `init`, `schema`, `validate-plan`, `check`, and `implement`;
- config keys created by `init`;
- plan frontmatter rules;
- quality YAML structure; and
- common failure cases.

## Tests

Add focused tests for:

- root CLI help listing new commands;
- `developer init` interactive success path;
- file generation in an isolated filesystem;
- no-silent-overwrite behavior;
- `developer schema plan` output shape;
- `developer schema quality` output shape; and
- generated sample plan passing `validate-plan` when intended.

## Acceptance Criteria

- `developer init` scaffolds a minimal usable setup in a clean repository.
- The generated config points to the generated prompt and check files correctly.
- `developer schema plan` and `developer schema quality` emit valid JSON Schema.
- `README.md`, `docs/getting-started.md`, and `docs/reference.md` describe the new onboarding flow.
- The prompt-path inconsistency is removed or explicitly resolved as part of this work.

## Out of Scope Follow-Ups

Capture separately later if still needed:

- non-interactive `init` automation flags such as `--yes` and explicit path flags;
- richer scaffolds for reviewers, fitness suites, and workspace configuration;
- config schema export;
- a generated documentation site; and
- broader migration help for already-customized repositories.
