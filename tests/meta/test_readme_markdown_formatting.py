from __future__ import annotations

from pathlib import Path


def _slice_markdown_section(body: str, *, header: str) -> str:
    """Return the Markdown section body starting at `header`.

    The slice includes the header line and stops before the next "## " header.
    """

    lines = body.splitlines(keepends=True)
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.rstrip("\n") == header:
            start_idx = idx
            break

    assert start_idx is not None, f"README.md missing expected header: {header!r}"

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].startswith("## "):
            end_idx = idx
            break

    return "".join(lines[start_idx:end_idx])


def _iter_lines_without_trailing_newlines(body: str) -> list[str]:
    return body.splitlines()


def test_readme_quickstart_does_not_overindent_fenced_blocks(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    quickstart = _slice_markdown_section(
        readme,
        header="## Quickstart from PyPI (no clone)",
    )

    # In ordered lists, 4 leading spaces is commonly interpreted as an indented code
    # block. Keep fenced blocks inside the Quickstart list at <= 3 spaces so they
    # render consistently as fenced blocks, not indented code blocks.
    assert "\n    ```" not in quickstart, (
        "README.md Quickstart contains a 4-space-indented fenced block; this is likely "
        "to render as an indented code block in some Markdown renderers"
    )


def test_readme_quickstart_avoids_deep_indent_outside_code_fences(
    repo_root: Path,
) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    quickstart = _slice_markdown_section(
        readme,
        header="## Quickstart from PyPI (no clone)",
    )
    lines = _iter_lines_without_trailing_newlines(quickstart)

    in_fence = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip(" ")

        if stripped.startswith("```"):
            in_fence = not in_fence
            continue

        if in_fence:
            continue

        if not stripped:
            continue

        leading_spaces = len(line) - len(stripped)
        assert leading_spaces < 4, (
            f"README.md Quickstart line {idx} is indented {leading_spaces} spaces outside "
            "a fenced code block; 4-space indentation is often rendered as code"
        )


def test_readme_documents_precommit_missing_path_remediation(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "pre-commit install" in readme, (
        "README.md should include a concrete remediation step for when `pre-commit` is "
        "missing from PATH (e.g. run `pre-commit install` manually after installing it)"
    )


def test_readme_process_prompt_has_no_trailing_whitespace(repo_root: Path) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "readme_process.md"
    body = prompt_path.read_text(encoding="utf-8")

    for idx, line in enumerate(_iter_lines_without_trailing_newlines(body), start=1):
        assert line == line.rstrip(" \t"), (
            f"{prompt_path} line {idx} has trailing whitespace"
        )
