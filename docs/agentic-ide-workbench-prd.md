# PRD: Multi-Repo Agentic IDE / Workbench

## Summary

Build an experimental **agentic IDE/workbench** in a fresh repository.

This product is a **local-first, review-first development environment** where humans coordinate work across multiple repositories and tasks while agents perform implementation inside isolated workspaces.

The workbench should let a user:

- switch between repositories and tasks on the fly;
- plan work;
- launch multiple agent runs in parallel;
- inspect repository and workspace files for context;
- review generated diffs locally;
- leave structured review comments;
- feed those comments back to the agent;
- either merge directly from the workbench or publish a pull request; and
- later import remote review comments back into the same review model.

This is **not** a general-purpose text editor. It is an **agent-native software workbench**.

## Reference

This project starts in a **new repository**.

Engineeringagent is a reference for concepts such as workspaces, planning, and agent orchestration:

- https://github.com/soetang/engineeringagent

ACP is relevant primarily for planning and session concepts:

- https://agentclientprotocol.com/get-started/introduction

## Vision

Create a **true agentic IDE**:

> A development environment where agents implement changes in isolated workspaces, humans review the results through a diff-first workflow, and feedback—local or remote—can be sent back to the agent in a structured loop.

## Problem

Existing agent tools are often:

- single-repo oriented;
- chat-first rather than review-first;
- awkward for parallel exploration;
- weak at preserving feedback loops; and
- poor at helping users move fluidly across repos, tasks, runs, and reviews.

We want a system where the human acts as an operator, reviewer, and approver across many concurrent streams of work, while agents do implementation safely in isolated workspaces.

It is also important that task execution follows the same general workflow philosophy as Engineeringagent: **short iterations with checks and review gates**, not long unbroken coding runs followed by one large review at the end.

## Users

### Initial users

- technical developers comfortable with git;
- solo developers or small teams;
- users experimenting with agent-driven implementation; and
- users who want local control with optional remote execution.

### Later users

- teams using GitHub or Azure DevOps;
- users working across many repositories; and
- developers who prefer running agents on remote/devbox machines over SSH.

## Product Principles

- **Multi-repo by default**
- **Diff-first, not editor-first**
- **Inspection is important even when editing is agent-driven**
- **Review is first-class**
- **Workspaces are execution sandboxes**
- **Context switching should be cheap**
- **Local and remote review should share one model**
- **Execution should work locally or remotely over SSH**
- **Publishing is optional; review should happen before publication**
- **The human orchestrates; the agent implements**
- **Implementation should happen through short, gated iterations**
- **Workflow primitives should be user-configurable**

## Core Concepts

### Repository

A known codebase managed by the workbench.

### Task

A unit of work within a repository.

### Planning Session

A planning or clarification session associated with a repository and task.

### Workspace

An isolated working environment for implementation, typically backed by a git worktree or equivalent mechanism.

### File Inspection

Read-only browsing of repository or workspace files so the human can inspect surrounding context, understand changes, and review code beyond the diff when needed.

### Run

One agent execution attempt inside a workspace.

### Review Snapshot

A reviewable diff state relative to a base branch.

### Review Thread

A comment thread attached to a file, line, hunk, or range in a review snapshot.

### Feedback Packet

A normalized set of unresolved comments and summary feedback sent back to the agent.

### Publication

A branch and optionally a pull request created from a workspace.

### Workflow Primitive

A configurable unit in the task flow. Primitives should include:

- deterministic transforms, such as CLI commands or scripts;
- checks, such as tests, linters, formatters, or validators;
- reviews, including agent-driven review steps; and
- implementation steps that use an agent to make changes.

The user should be able to configure which primitives run, in what order, and under which conditions.

## Core User Flows

### 1. Multi-repo switching

1. User sees multiple repositories in one workbench.
2. User switches between repositories and tasks freely.
3. State is preserved per repository, task, workspace, and planning/review context.
4. User can jump between planning, runs, and review at will.

### 2. Plan → implement → local review → direct merge

1. User selects repository and task.
2. User creates or refines a plan.
3. User launches an implementation run in a new workspace.
4. The agent works in short iterations rather than one long pass.
5. Checks and review gates run during the implementation flow.
6. User reviews the diff locally.
7. User leaves comments or approves.
8. User either:
   - sends feedback back to the agent; or
   - merges directly.

### 3. Plan → implement → local review → publish pull request

1. User reviews locally first.
2. User publishes branch and opens a pull request.
3. Other humans review in GitHub or Azure DevOps.
4. Remote comments can be imported back into the app.
5. Imported comments normalize into the same review model as local comments.
6. User sends unresolved feedback back to the agent.
7. Agent revises in the same workspace.
8. User re-reviews and republishes or merges.

### 4. Parallel exploration

1. User launches multiple runs for one task or multiple tasks.
2. Each run gets its own isolated workspace.
3. User reviews results independently.
4. User chooses one path to continue.

### 5. Remote execution over SSH

1. User connects to a remote execution target.
2. Agent runs happen remotely.
3. UI remains local.
4. Review and task switching remain unified in one workbench.

## Goals

### Product goals

- Make multi-repo, multi-task agent work manageable in one interface.
- Make review the central human interaction model.
- Make agent feedback structured and repeatable.
- Support both solo direct-merge workflows and team PR workflows.
- Allow execution to move off the local machine when needed.
- Preserve Engineeringagent-style implementation discipline: short iterations, checks, and review gates.
- Make the workflow configurable through reusable primitives rather than hardcoded one-off flows.

### MVP goals

- Register multiple repositories.
- Navigate tasks per repository.
- Start multiple isolated runs.
- Keep workspaces alive after runs complete.
- Inspect files in repositories and workspaces.
- Review diffs locally.
- Add inline comments and overall review feedback.
- Feed unresolved comments back to the agent.
- Rerun in the same workspace.
- Either merge directly or publish a pull request.

## Non-Goals

- Full source editing.
- Building a general-purpose code editor.
- Real-time multi-user collaboration.
- Perfect GitHub/Azure review synchronization in v1.
- Cloud multi-tenant infrastructure.
- Using ACP as the runtime protocol for every subsystem.
- Desktop packaging in the first version.

## Functional Requirements

### Multi-repo and task navigation

- The system must allow users to register and manage multiple repositories.
- The system must let users switch quickly between repositories and tasks.
- The system must preserve planning, run, and review state per repository and task.

### Workspace and run management

- The system must create a new isolated workspace for a new run.
- The system must support multiple active runs across repositories and tasks.
- The system must show run status and key metadata.
- The system must preserve a workspace after a run completes.
- The system must support rerunning in the same workspace.

### Iterative implementation flow

- Task execution should follow the same general flow philosophy as Engineeringagent.
- The agent should work in short iterations rather than long uninterrupted implementation passes.
- Checks should run during the implementation loop, not only at the very end.
- Review gates should be part of the task flow.
- The workbench should surface iteration state, gate/check outcomes, and review feedback clearly enough for the human to understand how the run is progressing.
- The product should support repeated cycles of implement → check → review → revise within the same workspace.

### Configurable workflow primitives

- The system must allow the user to configure task flows from reusable primitives.
- The primitive model should support deterministic transforms such as commands or scripts.
- The primitive model should support checks such as tests, linting, formatting, static analysis, schema validation, or similar repository-specific commands.
- The primitive model should support review steps, including agent-based reviews.
- The primitive model should support implementation steps that invoke an agent.
- The system should allow different repositories or tasks to use different configured primitive sequences.
- The system should make it clear which primitives are deterministic command/script steps versus agent-driven steps.
- Primitive outcomes should be visible in the run timeline so the human can understand what happened during each short iteration.

### Review

- The system must show changed files.
- The system must show a diff against a base branch.
- The system must allow inline comments on lines or hunks.
- The system must allow an overall review summary.
- The system must track review comment state: open, resolved, outdated.

### File inspection

- The system must allow the user to browse repository and workspace files.
- The system must allow the user to open files for read-only inspection.
- The system should make it easy to move from a diff to the surrounding file context.
- The system should support inspecting files that are unchanged when needed for understanding the task or review context.
- File inspection should support the review workflow but does not require full editing capabilities.

### Feedback loop

- The system must collect unresolved review comments.
- The system must package them into structured feedback.
- The system must send that feedback back to the agent.
- The system must support repeated review/revision cycles in the same workspace.

### Publish or merge

- The system must support direct merge from the workbench.
- The system must support publishing a branch and opening a pull request.

### Remote review import

- The system should support importing review comments from GitHub.
- The system should support importing review comments from Azure DevOps.
- Imported comments should be represented using the same internal review model as local comments.

### Remote execution

- The architecture must support local execution.
- The architecture must support remote execution over SSH.
- The UI must not assume repositories live on the same machine as the UI.

## Review Model Requirements

The system should use one normalized internal review model for:

- local review comments;
- imported GitHub comments; and
- imported Azure DevOps comments.

Minimum conceptual fields:

- repository id;
- task id;
- workspace id;
- run id;
- snapshot id;
- file path;
- line, range, or hunk anchor;
- author/source;
- comment body;
- status: open, resolved, outdated; and
- origin: local, GitHub, Azure.

## UX Requirements

The product should feel like:

- a lightweight IDE/workbench;
- a multi-repo operator console; and
- a review-first development environment.

### Primary screens

1. **Workbench / home**
   - repositories;
   - active tasks;
   - active runs; and
   - reviews awaiting attention.
2. **Repository/task view**
   - planning context;
   - task list; and
   - run list.
3. **Run/workspace detail**
   - status;
   - branch/base;
   - commits;
   - logs; and
   - actions.
4. **Review view**
   - changed files;
   - diff viewer;
   - inline comments; and
   - overall review decision/actions.
5. **File inspection view**
   - repository/workspace file tree;
   - read-only file viewer; and
   - navigation between diff hunks and full-file context.

## Architecture Requirements

The system should use **hexagonal architecture / ports and adapters**.

### Core architectural rule

Core domain and application logic must remain independent of:

- frontend framework;
- HTTP transport;
- persistence technology;
- git CLI details;
- SSH implementation details;
- GitHub or Azure APIs;
- ACP integration; and
- desktop shell concerns.

### Domain dependency rule

The **domain layer must have no external dependencies**.

In particular, domain code should not depend on:

- web frameworks;
- database libraries or ORMs;
- git libraries or CLI wrappers;
- SSH libraries;
- frontend or UI packages;
- ACP or agent SDKs;
- Pydantic or similar framework-bound validation layers; or
- any infrastructure adapter packages.

The domain should be implemented using standard-library Python wherever possible, with plain domain models, rules, and invariants.

### Suggested layers

#### Domain

Owns:

- repositories;
- tasks;
- workspaces;
- runs;
- review snapshots;
- review threads;
- feedback packets; and
- publication decisions.

#### Application

Owns use cases such as:

- register repository;
- create task;
- start run;
- rerun with feedback;
- list runs;
- create review comment;
- approve or reject review;
- publish pull request;
- merge workspace; and
- import external review comments.

#### Ports

Define interfaces for:

- workflow primitive execution;
- workspace lifecycle;
- run execution;
- diff generation;
- planning backend;
- persistence;
- review import/export;
- publication;
- merge;
- event streaming; and
- remote execution.

#### Adapters

Implement ports with:

- command/script execution adapters;
- local git CLI;
- local workspace provider;
- local process runner;
- SSH-backed remote runner;
- SQLite persistence;
- GitHub adapter;
- Azure DevOps adapter;
- ACP planning adapter;
- HTTP/WebSocket API; and
- web frontend.

### Modeling note

The core should be modeled around explicit entities such as:

- `Repository`
- `Task`
- `Workspace`
- `Run`
- `ReviewSnapshot`

It should not be centered around a single global current working directory.

## Technical Constraints

### Backend

- Python.
- Strong typing.
- API/service layer suitable for a local-first app.
- Support for both local and remote execution modes.

### Frontend

- Web-first.
- Read-only/diff-first rather than edit-first.

### Persistence

- Local persistence is acceptable for MVP.
- Persistence must support querying across repositories, tasks, runs, and reviews.

### Execution model

- Local execution must be supported.
- Remote execution over SSH must be supported conceptually and architecturally.
- Preferred remote model:
  - local UI;
  - remote backend/service; and
  - communication through SSH tunnel or equivalent secure channel.

## Testing Requirements

### Backend testing

Include automated tests for:

- domain logic;
- application use cases; and
- adapter integrations where needed.

Examples:

- run lifecycle;
- review thread lifecycle;
- feedback packet generation;
- publication decision logic; and
- workspace provisioning behavior.

### UX / end-to-end testing

Use **Playwright** for critical user flows.

Priority Playwright flows:

1. switch between repositories;
2. open a task;
3. start a run;
4. view a diff;
5. inspect surrounding file context;
6. add an inline review comment;
7. send unresolved feedback back to the agent;
8. observe rerun state update; and
9. choose merge or publish pull request flow.

The goal is not exhaustive UI coverage, but strong confidence in the main operator workflows.

## ACP Role

ACP is in scope primarily for **planning**, not necessarily for the entire runtime.

ACP may be used for:

- planning sessions;
- clarifications; and
- plan updates.

Run, workspace, review, and publication lifecycle can use native application APIs.

## Risks and Open Questions

- How to anchor comments robustly across reruns.
- Whether v1 should support line comments, hunk comments, or both.
- How much compare-runs UX belongs in MVP.
- How remote review import/export should work conceptually.
- Whether implementation and publication should be decoupled from the start.
- How automatic repository and task discovery should be versus explicit registration.

## Success Criteria

The experiment is successful if a user can:

1. register and switch between multiple repositories;
2. manage multiple tasks across those repositories;
3. launch two or more isolated implementation runs;
4. review one run locally through a diff UI;
5. leave structured review comments;
6. send comments back to the agent;
7. receive a revised result in the same workspace; and
8. either merge directly or publish a pull request.

## Short Build Brief

Build an experimental multi-repo agentic IDE/workbench in a fresh repository. Use Engineeringagent as a conceptual reference via https://github.com/soetang/engineeringagent, not as the implementation base. The system should let a human switch between repositories and tasks freely, launch multiple implementation runs in isolated workspaces, review changes locally in a diff-first UI, leave inline review comments, and send unresolved feedback back to the agent for revision in the same workspace. The user should be able to either merge directly or publish a pull request for external review. The architecture should use hexagonal design with replaceable ports and adapters, support local and future SSH-backed remote execution, and include backend tests plus Playwright coverage for key UX flows.
