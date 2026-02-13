# Fitness Rule Catalog

This file is generated from active manifest-declared fitness rules.

## Active Rules

| Rule ID | Severity | Adapter | Source | Scope | Summary |
| --- | --- | --- | --- | --- | --- |
| `architecture.dep-directionality` | error | python | builtin | `src/engineeringagent` | Enforce core module import direction boundaries. |
| `architecture.loop-subprocess-boundary` | error | python | builtin | `src/engineeringagent` | Enforce subprocess allowlist boundaries for command adapters/clients. |
| `architecture.prompt-locality` | error | python | builtin | `src/engineeringagent` | Keep canonical loop prompt content and template reads localized. |

## Rule Details

### `architecture.dep-directionality`

- Name: Dependency directionality
- Side-effect free: `true`
- Rationale: Keeps orchestration and contracts layered for reviewability.
- Remediation: Refactor imports to follow the declared architecture boundaries.

### `architecture.loop-subprocess-boundary`

- Name: Loop subprocess boundary
- Side-effect free: `true`
- Rationale: Centralizes command execution paths for consistent control.
- Remediation: Move OpenCode command execution to engineeringagent.opencode.client and Git command execution to engineeringagent.git.client.

### `architecture.prompt-locality`

- Name: Prompt locality
- Side-effect free: `true`
- Rationale: Prevents prompt drift and duplicate canonical wording across modules.
- Remediation: Move canonical prompt text and template reads to engineeringagent.prompts templates/renderer modules.

