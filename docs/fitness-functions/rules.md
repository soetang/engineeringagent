# Fitness Rule Catalog

This file is generated from active manifest-declared fitness rules.

## Active Rules

| Rule ID | Severity | Adapter | Source | Scope | Summary |
| --- | --- | --- | --- | --- | --- |
| `architecture.dep-directionality` | error | python | builtin | `src/engineeringagent` | Enforce core module import direction boundaries. |
| `architecture.loop-facade-line-budget` | error | command | custom | `src/engineeringagent/loop.py` | Enforce a permanent line budget cap for the loop facade. |
| `architecture.loop-subprocess-boundary` | error | python | builtin | `src/engineeringagent` | Enforce subprocess allowlist boundaries for command adapters/clients. |
| `architecture.markdown-locality-reference-coverage` | error | python | builtin | `repository markdown (*.md)` | Restrict markdown to approved paths and require non-doc markdown files to be referenced in-repo. |
| `architecture.no-non-ignorable-ruff-suppressions` | error | command | custom | `src tests harness` | Block suppression directives for configured high-value Ruff rules. |
| `architecture.no-stdlib-dataclasses-in-src` | error | command | custom | `src/engineeringagent` | Block stdlib dataclasses usage in production source models. |
| `architecture.prompt-locality` | error | python | builtin | `src/engineeringagent` | Keep canonical loop prompt content and template reads localized. |
| `architecture.scaffold-template-locality` | error | python | builtin | `src/engineeringagent` | Keep scaffold template payloads in scaffold_templates assets. |

## Rule Details

### `architecture.dep-directionality`

- Name: Dependency directionality
- Side-effect free: `true`
- Rationale: Keeps orchestration and contracts layered for reviewability.
- Remediation: Refactor imports to follow the declared architecture boundaries.

### `architecture.loop-facade-line-budget`

- Name: Loop facade line budget
- Side-effect free: `true`
- Rationale: Keeps engineeringagent.loop concise as the compatibility facade seam.
- Remediation: Move non-control-flow internals into engineeringagent.loop_runtime modules.

### `architecture.loop-subprocess-boundary`

- Name: Loop subprocess boundary
- Side-effect free: `true`
- Rationale: Centralizes command execution paths for consistent control.
- Remediation: Move OpenCode command execution to engineeringagent.opencode.client and Git command execution to engineeringagent.git.client.

### `architecture.markdown-locality-reference-coverage`

- Name: Markdown locality and reference coverage
- Side-effect free: `true`
- Rationale: Prevents markdown sprawl and orphaned non-doc markdown assets across repository zones.
- Remediation: Move markdown under approved roots and add at least one deterministic in-repo reference for each markdown file outside docs/.

### `architecture.no-non-ignorable-ruff-suppressions`

- Name: No non-ignorable Ruff suppressions
- Side-effect free: `true`
- Rationale: Keep lint policy enforceable by requiring refactor-first remediation.
- Remediation: Remove inline/file-level ignore directives and refactor; for PLR0913, group related arguments into a NamedTuple or pydantic model.

### `architecture.no-stdlib-dataclasses-in-src`

- Name: No stdlib dataclasses in src
- Side-effect free: `true`
- Rationale: Enforces a single Pydantic BaseModel contract in src/engineeringagent.
- Remediation: Replace stdlib dataclasses usage with pydantic.BaseModel models.

### `architecture.prompt-locality`

- Name: Prompt locality
- Side-effect free: `true`
- Rationale: Prevents prompt drift and duplicate canonical wording across modules.
- Remediation: Move canonical prompt text and template reads to engineeringagent.prompts templates/renderer modules.

### `architecture.scaffold-template-locality`

- Name: Scaffold template locality
- Side-effect free: `true`
- Rationale: Prevents init scaffold regressions from drifting back to inline template payloads in source modules.
- Remediation: Move scaffold template bodies to engineeringagent.scaffold_templates assets and load them via engineeringagent.init_scaffold.

