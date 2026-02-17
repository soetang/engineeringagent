# Fitness Rule Catalog

This file is generated from active manifest-declared fitness rules.

## Active Rules

| Rule ID | Severity | Adapter | Source | Scope | Summary |
| --- | --- | --- | --- | --- | --- |
| `architecture.dep-directionality` | error | command | custom | `src/engineeringagent` | Enforce core module import direction boundaries. |
| `architecture.docs-allowlist-policy` | error | command | custom | `docs_root markdown (*.md) excluding docs_root/spec/**` | Require each docs_root markdown file to be listed in exactly one policy list. |
| `architecture.harness-root-yaml-only` | error | command | custom | `harness/ (regular files at root)` | Enforce YAML-only regular files directly under harness root. |
| `architecture.harness-src-import-allowlist` | error | command | custom | `harness/fitness-functions` | Restrict harness fitness functions to a narrow supported engineeringagent surface. |
| `architecture.loop-facade-line-budget` | error | command | custom | `src/engineeringagent/loop.py` | Enforce a permanent line budget cap for the loop facade. |
| `architecture.loop-subprocess-boundary` | error | command | custom | `src/engineeringagent` | Enforce subprocess allowlist boundaries for command adapters/clients. |
| `architecture.markdown-locality-reference-coverage` | error | command | custom | `repository markdown (*.md)` | Restrict markdown to approved paths and require non-doc markdown files to be referenced in-repo. |
| `architecture.no-doc-content-tests` | error | command | custom | `tests` | Prevent pytest from asserting exact wording in README/docs markdown. |
| `architecture.no-env-key-reads` | error | command | custom | `src/ harness/ tests/` | Forbid env-key reads (os.getenv, os.environ.get, os.environ['X'], 'X' in os.environ). |
| `architecture.no-facade-varargs-shims` | error | command | custom | `src/engineeringagent` | Block facade varargs shims, __signature__ masking, and hidden kwargs dropping. |
| `architecture.no-non-ignorable-ruff-suppressions` | error | command | custom | `src tests harness` | Block suppression directives for configured high-value Ruff rules. |
| `architecture.no-stdlib-dataclasses-in-src` | error | command | custom | `src/engineeringagent` | Block stdlib dataclasses usage in production source models. |
| `architecture.progress-log-path-locality` | error | command | custom | `src/engineeringagent` | Centralize loop progress artifact paths and writes behind approved helpers. |
| `architecture.prompt-locality` | error | command | custom | `src/engineeringagent` | Keep canonical loop prompt content and template reads localized. |
| `architecture.retry-feedback-no-truncation` | error | command | custom | `src/engineeringagent/prompts/renderer.py` | Block truncation-by-slicing in retry feedback prompt injection. |
| `architecture.scaffold-docs-exact-sync` | error | command | custom | `docs and src/engineeringagent/scaffold_templates` | Enforce byte-for-byte sync between selected docs and scaffold templates. |
| `architecture.scaffold-template-agents-doc-links` | error | command | custom | `src/engineeringagent/scaffold_templates/AGENTS.md` | Require scaffolded reference docs to be linked from scaffold AGENTS.md. |
| `architecture.scaffold-template-locality` | error | command | custom | `src/engineeringagent` | Keep scaffold template payloads in scaffold_templates assets. |
| `architecture.source-first-loop-command-policy` | error | command | custom | `docs/spec/features/*.yaml and harness/checks.yaml` | Enforce source-first workspace execution for loop command surfaces. |
| `smoke.opencode-real-hello-world` | error | command | custom | `repository (temp repo)` | Validate the real agent loop end-to-end in an isolated temp repository. |

## Rule Details

### `architecture.dep-directionality`

- Name: Dependency directionality
- Side-effect free: `true`
- Rationale: Keeps orchestration and contracts layered for reviewability.
- Remediation: Refactor imports to follow the declared architecture boundaries.

### `architecture.docs-allowlist-policy`

- Name: Docs allowlist policy
- Side-effect free: `true`
- Rationale: Keeps docs additions explicit and reviewable by classifying each file as human-facing or agent-facing.
- Remediation: Add every docs markdown file to exactly one of human_docs or agent_docs in harness/scaffold_policy.yaml.

### `architecture.harness-root-yaml-only`

- Name: Harness root YAML-only
- Side-effect free: `true`
- Rationale: Keeps harness root manifest-only and prevents executable/policy file sprawl at repository root policy surfaces.
- Remediation: Move non-YAML root files under harness/fitness-functions or another harness subdirectory; keep only *.yaml/*.yml files at harness root.

### `architecture.harness-src-import-allowlist`

- Name: Harness-to-src import allowlist
- Side-effect free: `true`
- Rationale: Prevents harness scripts from depending on orchestration/runtime internals that are not part of the supported authoring API.
- Remediation: Replace forbidden imports with the supported helpers under engineeringagent.fitness.*.

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

### `architecture.no-doc-content-tests`

- Name: No doc-content tests
- Side-effect free: `true`
- Rationale: Doc wording is intentionally flexible; tests should cover functionality instead.
- Remediation: Delete or refactor tests that read README.md or docs/**/*.md and assert substrings.

### `architecture.no-env-key-reads`

- Name: No env-key reads
- Side-effect free: `true`
- Rationale: Environment variable config is ad-hoc and hard to discover; configuration must come from engineeringagent.toml.
- Remediation: Remove env-key reads; load configuration from engineeringagent.toml (with pyproject fallback) and pass explicit values through contracts.

### `architecture.no-facade-varargs-shims`

- Name: No facade varargs shims
- Side-effect free: `true`
- Rationale: Keeps loop orchestration contracts explicit and typed instead of compatibility shims.
- Remediation: Replace varargs facade wrappers with explicit typed contracts and remove hidden kwargs dropping.

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

### `architecture.progress-log-path-locality`

- Name: Progress log path locality
- Side-effect free: `true`
- Rationale: Prevents regressions that reintroduce inline progress/log path literals or direct file writes.
- Remediation: Construct paths via engineeringagent.progress.paths and write loop log sinks via engineeringagent.progress.logging.

### `architecture.prompt-locality`

- Name: Prompt locality
- Side-effect free: `true`
- Rationale: Prevents prompt drift and duplicate canonical wording across modules.
- Remediation: Move canonical prompt text and template reads to engineeringagent.prompts templates/renderer modules.

### `architecture.retry-feedback-no-truncation`

- Name: Retry feedback no truncation
- Side-effect free: `true`
- Rationale: Prevents prompt retries from losing the most relevant failure details.
- Remediation: Remove truncation-by-slicing from retry feedback injection; bound retry feedback by contract caps and canonical re-serialization.

### `architecture.scaffold-docs-exact-sync`

- Name: Scaffold docs exact sync
- Side-effect free: `true`
- Rationale: Prevents drift between canonical docs/ and init scaffold templates.
- Remediation: Update scaffold template files to match canonical docs per harness/scaffold_policy.yaml.

### `architecture.scaffold-template-agents-doc-links`

- Name: Scaffold template AGENTS doc links
- Side-effect free: `true`
- Rationale: Keeps scaffolded reference docs discoverable and prevents drift between what init scaffolds and what AGENTS.md points users to.
- Remediation: Add missing links and short descriptions for each scaffolded reference doc in src/engineeringagent/scaffold_templates/AGENTS.md.

### `architecture.scaffold-template-locality`

- Name: Scaffold template locality
- Side-effect free: `true`
- Rationale: Prevents init scaffold regressions from drifting back to inline template payloads in source modules.
- Remediation: Move scaffold template bodies to engineeringagent.scaffold_templates assets and load them via engineeringagent.init_scaffold.

### `architecture.source-first-loop-command-policy`

- Name: Source-first loop command policy
- Side-effect free: `true`
- Rationale: Prevent stale cached package artifacts from bypassing current workspace source.
- Remediation: Replace forbidden in-repo uvx self-invocations with source-first forms; prefer uv run engineeringagent ...

### `smoke.opencode-real-hello-world`

- Name: Real OpenCode hello-world smoke
- Side-effect free: `true`
- Rationale: Catches regressions where the OpenCode subprocess/loop stops mid-implementation.
- Remediation: Enable via engineeringagent.toml ([harness.fitness] opencode-real-smoke = true) and resolve reported loop/setup errors.

