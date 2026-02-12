# Spec Writing Guide (LLM-Oriented)

## Purpose

- Define how agents create new feature specs for this repository.
- Ensure every new spec starts with a short user interview before drafting YAML.

## Hard Rule

- Do not draft a new `docs/spec/features/FEAT-*.yaml` file until you complete a user interview and the user confirms scope.

## Mandatory Interview Flow

1. Ask targeted questions first (no spec draft yet).
2. Capture answers in a concise scope summary.
3. Ask for explicit confirmation on the summary.
4. Draft the feature spec only after confirmation.

## Minimum Interview Topics

- Problem statement: what pain this feature solves.
- Scope boundary: what is in scope vs out of scope.
- Success criteria: how the user will judge completion.
- Constraints: safety, compatibility, or workflow constraints.
- Verification expectations: required commands or checks.

## Question Quality Bar

- Ask specific, decision-shaping questions; avoid generic filler.
- Prefer 3-7 focused questions over one broad question.
- If tradeoffs exist, present options and recommend a default.

## Drafting Rules After Interview

- Follow `docs/spec/schemas/feature.schema.json` exactly.
- Use one feature file with nested subtasks.
- Keep acceptance criteria outcome-based and testable.
- Keep verification commands concrete and executable.
- Preserve repository language and conventions used in existing FEAT files.

## Post-Draft Commit Workflow

After creating or updating a spec file, commit it in the same loop so state is recoverable.

1. Validate specs before commit:
   - `uv run python scripts/validate_specs.py`
2. Stage only the intended spec/doc files:
   - `git add docs/spec/features/FEAT-*.yaml`
   - Add related doc updates when applicable.
3. Use a clear commit message focused on intent:
   - Example: `spec: add FEAT-007 path-first run CLI`
4. Create the commit:
   - `git commit -m "spec: add FEAT-007 path-first run CLI"`
5. Verify clean result:
   - `git status --short`

Notes:

- Keep one logical spec change per commit.
- Do not include unrelated code refactors in the same spec commit.

## Suggested Interview Summary Template

- Goal:
- In scope:
- Out of scope:
- Constraints:
- Done looks like:
- Verification signals:

## Definition of Ready for Spec Drafting

- User interview completed.
- Scope summary confirmed by user.
- Open questions resolved or explicitly deferred.

## If User Asks to "Just Write the Spec"

- Still run a brief interview (minimum 3 focused questions).
- Keep it fast, then draft immediately after answers.
