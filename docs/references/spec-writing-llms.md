# Spec Writing Guide (LLM-Oriented)

## Purpose

- Define how agents create new feature specs for this repository.
- Ensure every new spec starts with a short user interview before drafting YAML.

## Hard Rule

- Do not draft a new `docs/spec/features/FEAT-*.yaml` file until you complete a user interview and the user confirms scope.
- If the feature changes any API/contract behavior, explicit contract-delta documentation is mandatory and high priority in the spec (old behavior -> new behavior, compatibility policy, migration/rollout expectation).

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
- Contract impact: which interfaces/behaviors change, whether compatibility is required, and whether migration is one-time or phased.

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
- Require an explicit fitness-function impact assessment for every new spec.
  - If fitness functions must change, name the affected rules/scripts and expected updates.
  - If no fitness updates are needed, record the exact statement "no fitness-function changes required" with a brief justification.
- For contract/API changes, encode explicit deltas in spec text (typically `constraints`, `implementation_notes`, and `acceptance`) including:
  - changed surfaces (schema/model, CLI/runtime behavior, prompt contract, docs),
  - exact old vs new behavior,
  - compatibility/deprecation policy,
  - migration scope and rollback/fallback expectations.

## Spec Creation Checklist

- Include required top-level fields in every active feature spec:
  - `type` (one of: `feature`, `bug`, `spec`, `docs`, `chore`, `test`)
  - `expected_commit_subject` in `type: summary` format
- Keep the expected subject deterministic for the spec intent (example: `spec: add FEAT-016 commit message policy and spec typing`).
- Verify the spec validates before commit.
- Commit the spec/doc changes with the exact `expected_commit_subject` value.

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

## Contract Change Declaration (Required When Applicable)

- Include a dedicated contract-change block in the spec narrative (`implementation_notes` recommended).
- Use concrete statements, not implied intent.
- Minimum declaration format:
  - Surface: what contract changes.
  - Old behavior: what happens today.
  - New behavior: what must happen after implementation.
  - Compatibility policy: immediate break, temporary dual-support, or deprecation path.
  - Migration plan: which files/data/configs change and whether migration is one-time.
  - Verification evidence: tests/commands that prove the contract transition.

## If User Asks to "Just Write the Spec"

- Still run a brief interview (minimum 3 focused questions).
- Keep it fast, then draft immediately after answers.
