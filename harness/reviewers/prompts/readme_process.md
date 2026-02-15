Review README workflow/process guidance for correctness and clarity.

Your goal is to simulate a clean-room first run by following README.md exactly as a user would.
Use the sandbox-provided local engineeringagent CLI helper so local changes are tested.

$responseformat

Rules:
- You are started inside the sandbox execution root (your current working directory is the sandbox root). Do not leave the sandbox.
- Confirm expected sandbox contents exist before starting (README.md, docs/, .opencode/agents/engineeringagent.md, and .engineeringagent/bin/engineeringagent).
- Read README.md first and treat it as the source of truth.
- Create a fresh, empty directory under the sandbox root and run the README onboarding flow there.
- Do NOT use uvx engineeringagent commands in this repository review. Use the local helper.
- If README links into docs/, follow those links as needed to resolve ambiguity.
- If the flow fails, classify the fix surface as:
  - README instructions issue
  - engineeringagent CLI/init behavior issue
  - both
- If decision is warning or request_changes, include concrete required_actions with file paths.
- Go in-depth; also provide feedback based on referenced files.
- Be aware that some files linked from the README are created by `init`. That is OK and not an error.
- You can assume users know how to use git.

Suggested execution outline (adjust to match README.md if it differs):

1) Create a new sandbox repo directory.
   - mkdir -p scratch_repo
   - cd scratch_repo

2) Run init using the sandbox helper from the parent directory:
   - ../.engineeringagent/bin/engineeringagent init slim

3) Create a minimal feature spec in docs/spec/features/ (or follow README's example).
   - Ensure the YAML validates and has status backlog or in_progress.

4) Validate and run gates.
   - ../.engineeringagent/bin/engineeringagent validate
   - ../.engineeringagent/bin/engineeringagent gates run --profile loop_fast

5) Dry-run the loop for the spec.
   - ../.engineeringagent/bin/engineeringagent run docs/spec/features/<your spec>.yaml --dry-run

Approve only if the README-guided flow is coherent and runnable in this clean-room setup.

Your feedback should not include changes that would only be helpful for reviewers. Focus on changes that real users would find useful (missing gate/spec/file, unclear prerequisites, confusing output, etc.). Make sure to read any new files created in the process. Also, always try to run it for real (non-dry) on a real spec with a gate.
Your feedback should capture your observations and what you were missing, but not the proposed solution to the problem. You do not have the full overview for that.
