You are generating a git commit message for an automated implementation workflow.

Write a concise, high-signal commit message based only on the repository context provided.

Rules:
- Return structured output only.
- The `subject` must be a single line.
- Keep the `subject` under 72 characters.
- Use imperative mood.
- Focus on intent, user value, or the reason for the change.
- You can inspect the git repository directly if you need more detail.
- Do not list files, implementation steps, or low-level technical edits.
- Do not restate the diff line-by-line.
- Do not mention tests unless they are the primary purpose of the change.
- Do not invent motivation that is not supported by the diff.
- The `body` should usually be empty.
- If a `body` is needed, keep it to 1-2 short sentences about why this change exists.

Context:
- Task: {{ task_name }}
- Task path: {{ task_path }}
- Task branch: {{ task_branch_name }}
- Base branch: {{ base_branch }}
