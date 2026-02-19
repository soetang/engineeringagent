# Harness Engineering Principles

This document explains the human-first principles behind EngineeringAgent. It is written for operators who steer work, review outcomes, and decide what to run next.

The goal is simple: keep agent execution loops reliable under real-world constraints (limited context windows, imperfect model judgment, and changing requirements).

## 1) Ralph Loop: short cycles with external memory

Use short Ralph Loop iterations instead of long, fragile sessions. Each loop should do one incremental unit, verify it, and persist state in files so the next loop can start cleanly.

Why this helps:

- Context windows are finite, so long chats drift.
- Frequent resets reduce compounding mistakes.
- File-based state (specs, run logs, docs) makes progress recoverable.

## 2) Progressive disclosure: right detail at the right layer

Keep first-run guidance concise, then link to deeper references.

- `README.md` explains what the system is and how to run one loop.
- `AGENTS.md` maps deterministic execution rules.
- `docs/references/*.md` stores detailed agent-facing procedures.
- Domain docs (like this file) explain deeper concepts for humans.

This split lowers onboarding friction without hiding operational depth.

## 3) Structured YAML specs: deterministic units of work

Every feature runs from a structured YAML spec with explicit fields for objective, constraints, acceptance criteria, and subtasks.

Practical effect:

- Work selection is explicit (most important open subtask).
- Implementation follows explicit TDD sequencing (red -> green -> refactor).
- Progress is auditable (`status`, `updated_at`, run logs).
- Handoffs between humans and agents stay consistent.

## 4) Automatic validation: verify every loop

Each iteration should run automatic validation before claiming progress.

At minimum:

- Validate feature specs against schema/contracts.
- Run the requested docs/code checks for the current subtask.
- Record pass/fail outcomes in loop artifacts.

This keeps quality gates mechanical instead of relying on memory.

## 5) Fitness functions: protect architecture continuously

A fitness function is an executable check that protects an architectural or process property over time.

In this repository, gate profiles and validators serve as fitness functions for:

- Documentation structure and audience boundaries.
- Spec integrity and run-loop discipline.
- Repeatable quality checks that resist entropy.

## 6) Agent reviewer: planned complement, not current default

Agent reviewer workflows are planned for judgment-heavy checks that deterministic validation cannot fully cover. They are not the primary control mechanism today.

Current default:

- Humans steer priorities and approve direction.
- Deterministic validators and gate profiles enforce baseline quality.

Planned direction:

- Add reviewer agents as a complement after deterministic checks pass.
- Keep review outputs auditable and scoped to clear criteria.

## External context

- OpenAI harness engineering overview: https://openai.com/index/harness-engineering/
- Ralph Loop background: https://ghuntley.com/ralph/
