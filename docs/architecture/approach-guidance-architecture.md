# Approach Guidance Architecture (FEAT-163 foundation)

## Purpose

Define the CLI-native guidance architecture that replaces scaffolded `docs/references/*` and
`docs/principles/*` handouts.

## Information architecture

- `engineeringagent approach` provides the canonical entrypoint.
- `engineeringagent approach list` emits deterministic topic ids and short titles.
- `engineeringagent approach <topic_id>` emits one topic document.
- `--output <path>` writes the rendered topic content to a file.

The architecture is progressive disclosure: one explicit overview + topic-level documents.

## Stable topic ids and aliases

Canonical ids are durable machine-facing tokens. Aliases are accepted for discoverability and
human convenience only.

| Canonical id        | Aliases                          | Source document                                  |
|---------------------|----------------------------------|--------------------------------------------------|
| `overview`          | _(none)_                         | `src/engineeringagent/approach/docs/overview.md` |
| `principles`        | `harness-engineering-principles`  | `src/engineeringagent/approach/docs/principles.md` |
| `workflow`          | _(none)_                         | `src/engineeringagent/approach/docs/workflow.md` |
| `specifications`    | `spec-writing`                   | `src/engineeringagent/approach/docs/specifications.md` |
| `quality-checks`    | `quality-check-playbook`          | `src/engineeringagent/approach/docs/quality-checks.md` |
| `reviewer-authoring`| `reviewer-authoring-guide`        | `src/engineeringagent/approach/docs/reviewer-authoring.md` |

Excluded from the user-facing surface:

- `docs/references/contributor-commands.md`
- `docs/references/documentation-practices.md`

## Contract notes

- Each source topic document stores `approach_id` frontmatter.
- A single markdown H1 acts as title; no duplicate title metadata layer is required.
- Migration keeps user-facing prose intact except approved edits.
- Canonical docs are loaded from package resources, not a scaffold sync copy.
