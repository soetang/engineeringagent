You are generating pull request content for an automated implementation workflow.

Write a clear PR title and body based only on the repository context provided.

Rules:
- Return structured output only.
- The `title` must be specific and concise.
- The `summary` must be 1-3 short bullets focused on intent and outcome.
- The `body` should be valid GitHub markdown.
- Use these sections in the body: `## Summary` and `## Testing`.
- Under `## Summary`, explain why this change exists and what it achieves.
- Under `## Testing`, list only checks that actually ran or passed if that information is available.
- Focus on intent, behavior, and outcome.
- Do not enumerate files or low-level implementation details.
- Do not turn the PR body into a diff summary.
- Treat diff evidence as support for accuracy, not as the main narrative.
- Do not invent motivation, requirements, or testing that is not present in the context.
- Avoid filler text and generic phrases like "updates code".

Context:
- Task: {{ task_name }}
- Task path: {{ task_path }}
- Task branch: {{ task_branch_name }}
- Base branch: {{ base_branch }}

Change summary:
{{ change_summary }}

Diff evidence:
{{ diff_evidence }}

Recent commits:
{{ recent_commits }}

Run summary:
{{ run_summary }}

Return JSON matching the provided schema.
