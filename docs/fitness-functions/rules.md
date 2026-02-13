# Fitness Rule Catalog

This file is generated from the active fitness-rule registry.

## Active Rules

| Rule ID | Severity | Adapter | Source | Scope | Summary |
| --- | --- | --- | --- | --- | --- |
| `architecture.dep-directionality` | error | python | builtin | `src/engineeringagent` | Enforce core module import direction boundaries. |
| `architecture.loop-subprocess-boundary` | error | python | builtin | `src/engineeringagent` | Enforce subprocess allowlist boundaries for command adapters/clients. |

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

