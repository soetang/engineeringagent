# Reviewer Authoring Guide

This guide is for humans creating or updating reviewer agents in a repository.
Use it when adding a new reviewer, changing reviewer scope, or migrating old prompt files.

## 1) Create a reviewer entry

Define the reviewer in `harness/reviewers.yaml`.

Minimum fields:

- `prompt_file`: repo-relative markdown path under `harness/reviewers/prompts/`
- `trigger.phase`: `iteration_end` or `feature_done`

Common optional fields:

- `trigger.on_change`: path globs that scope when the reviewer runs
- `approval.first_feature_approval`: boolean (default `true`)
- `sandbox.mode`: `temp_worktree_snapshot` (snapshot) or `empty_folder` (explicit-asset sandbox)
- `sandbox.assets`: list of repo-relative paths to include in an `empty_folder` sandbox (files or directories)
- `feedback_context`: optional string forwarded verbatim alongside reviewer feedback into the next implement pass.

Use `feedback_context` to describe reviewer scope limitations (for example, clean-room sandboxes that do not include `src/` or `tests/`) so implement treats failures as real but chooses fixes that align with the full repository and feature specs.

You can scaffold a baseline config and prompt set with:

```bash
uvx engineeringagent reviewers init
```

## 2) Author the prompt with the required response-format token

Create prompt markdown files under `harness/reviewers/prompts/`.

Every reviewer prompt must include a literal `$responseformat` placeholder.
That token is the only supported insertion point for the canonical response-format contract.

The canonical contract includes a machine-readable JSON Schema for the reviewer decision envelope.
At runtime, reviewer execution prefers OpenCode JSON event output and performs bounded same-session retries
when the returned decision object does not validate.

Important contract rules:

- Do include `$responseformat` in each prompt file.
- Do not duplicate or customize JSON envelope instructions in prompt prose.
- Do not rely on fallback behavior; prompts missing `$responseformat` fail validation/runtime contract checks.

## 3) Keep reviewer instructions focused on review intent

After `$responseformat`, keep the rest of the prompt specific to what the reviewer should evaluate:

- scope boundaries (which files or concerns to focus on)
- quality criteria (readability, correctness, docs/process, etc.)
- required evidence or failure reporting expectations

The decision envelope stays canonical (`decision`, `summary`, optional `required_actions`, `scope_notes`).

## 4) Migrate existing prompts

When migrating older reviewer prompts:

1. Remove bespoke output-format prose (for example, hand-written JSON field instructions).
2. Insert `$responseformat` where response-contract instructions should appear.
3. Keep reviewer-specific evaluation guidance that is not format boilerplate.
4. Run validation to catch contract issues.

Recommended checks:

```bash
uv run engineeringagent validate
uvx engineeringagent reviewers list
```

## 5) Troubleshooting

- If validation reports a prompt missing `$responseformat`, update that prompt file directly under `harness/reviewers/prompts/`.
- If reviewer output is malformed, the runtime parser emits a deterministic `request_changes` envelope.
- For full contract details and policy examples, see `docs/references/reviewer-agents-llms.md`.
