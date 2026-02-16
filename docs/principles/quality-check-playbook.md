# Quality Check Playbook

This guide explains when to use each quality check in this repository and how to design checks that are useful for both humans and agents.

The boundaries are not always perfectly clear: some checks overlap, and a single change can require multiple layers of verification.
Use this playbook as a practical default, then apply judgment based on risk.

## Verification Layers at a Glance

| Layer | Primary purpose | Typical scope | Examples |
| --- | --- | --- | --- |
| Unit tests (`pytest`) | Verify behavior and logic | Functions/modules/features | Expected outputs, edge cases, regressions |
| Fitness functions | Protect structural constraints and quality attributes over time | Architecture seams, layering, allowed patterns | Import boundaries, prompt locality, facade budgets |
| Linting (`ruff`) | Enforce code quality and consistency | Style, complexity, docs hygiene | Complexity limits, docstring completeness |
| Type checks (`pyright`) | Catch interface/type mismatches early | Cross-module contracts and API usage | Wrong argument types, missing attributes |
| Spec/contract validation | Ensure loop/spec integrity | Feature specs and schema conformance | YAML/schema validity |

## When to Run What

- During normal implementation loops:
  - `uv run python -m engineeringagent.cli gates run --profile loop_fast`
- Before commit or merge:
  - `uv run python -m engineeringagent.cli gates run --profile precommit`
- When editing feature specs or schema-related files:
  - `uv run python -m engineeringagent.cli validate`
- When debugging a specific class of failure:
  - Ruff: `uv run ruff check src/engineeringagent harness`
  - Pyright: `uv run pyright src/engineeringagent tests harness`
  - Unit tests: `uv run pytest -q`
  - Fitness functions: `uv run python -m engineeringagent.cli fitness run --format json`

## How to Think About Fitness Functions

Fitness functions are generally structural and quality-attribute-oriented checks.

Use them to protect long-lived properties such as:
- architecture boundaries
- layering and dependency direction
- invariants that should not drift over time
- maintainability constraints that are hard to enforce by convention alone

Unit tests and fitness functions can overlap, and that is fine:
- If the risk is "does behavior still work?" lean unit test.
- If the risk is "is the system still shaped correctly?" lean fitness function.
- If both risks apply, add both checks.

## Tip: Catch Common Errors, Not Every Possible Error

Fitness functions do not need to be perfect.
Their job is to catch common, high-impact regressions with low noise.

A failing rule should include a remediation comment that is specific enough to prevent cheating or superficial fixes.

Good remediation includes:
- what failed (rule and location)
- why it matters (risk or quality attribute)
- what to change (concrete refactor direction)
- how to verify (exact command)

Recommended failure format:

`Rule <id> failed at <path:line>. Why: <risk>. Fix: <specific change>. Verify: <command>.`

Avoid checks that can be satisfied by comment edits or keyword stuffing. Prefer executable or structure-aware checks.

## Practical Workflow

1. Run `loop_fast` while iterating.
2. Add or update unit tests for behavior changes.
3. Add or update fitness checks when introducing or protecting structural constraints.
4. Run `precommit` before finalizing.
5. If a check fails, fix root cause first. Relax thresholds or rules only with explicit rationale.
