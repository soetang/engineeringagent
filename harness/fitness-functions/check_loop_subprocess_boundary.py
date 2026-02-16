from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.loop-subprocess-boundary"
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_SEMGREP_RULE_CONFIG = Path(__file__).with_name("loop_subprocess_boundary_semgrep.yaml")
_MODULE_RULE_ID = "architecture.loop-subprocess-boundary.module-subprocess-calls"
_ATTRIBUTE_CALL_RE = re.compile(
    r"\b(?P<module>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*"
    r"(?P<call>run|Popen|call|check_call|check_output)\s*\("
)
_DIRECT_CALL_RE = re.compile(r"\b(?P<call>[A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _loop_subprocess_boundary_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        return [f"missing source package root: {_SOURCE_PACKAGE_ROOT}"]

    findings = _run_semgrep(project_root)
    results = findings.get("results")
    if not isinstance(results, list):
        raise ValueError("semgrep output missing 'results' list")

    violations = {
        _format_violation(project_root, finding)
        for finding in results
        if isinstance(finding, dict)
    }
    violations.discard("")
    return sorted(violations)


def _run_semgrep(project_root: Path) -> dict[str, object]:
    command = [
        "semgrep",
        "scan",
        "--config",
        str(_SEMGREP_RULE_CONFIG),
        "--json",
        "--quiet",
        "--metrics=off",
        "--disable-version-check",
        "--no-git-ignore",
        "--no-rewrite-rule-ids",
        ".",
    ]
    proc = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode not in {0, 1}:
        stderr = (proc.stderr or "").strip()
        message = f"semgrep exited with code {proc.returncode}"
        if stderr:
            message = f"{message}: {stderr}"
        raise ValueError(message)

    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise ValueError("semgrep produced empty stdout")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("semgrep output is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("semgrep output JSON must be an object")
    return payload


def _format_violation(project_root: Path, finding: dict[str, object]) -> str:
    path = _result_path(project_root, finding.get("path"))
    line = _result_line(finding)
    code_line = _result_code_line(project_root, finding, line)
    check_id = finding.get("check_id")

    if check_id == _MODULE_RULE_ID:
        call_expr = _attribute_call_expression(code_line)
        if call_expr is None:
            return ""
        return (
            f"{path}:{line} uses {call_expr}; move this command call to an approved "
            "client/adapter module"
        )

    call_name = _direct_call_name(code_line)
    return (
        f"{path}:{line} uses {call_name}(...) from subprocess; move this command call "
        "to an approved client/adapter module"
    )


def _result_path(project_root: Path, value: object) -> str:
    if not isinstance(value, str) or not value:
        return str(_SOURCE_PACKAGE_ROOT)

    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(project_root)
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def _result_line(finding: dict[str, object]) -> int:
    start = finding.get("start")
    if not isinstance(start, dict):
        return 1
    line = start.get("line")
    return line if isinstance(line, int) and line > 0 else 1


def _result_code_line(project_root: Path, finding: dict[str, object], line: int) -> str:
    extra = finding.get("extra")
    if not isinstance(extra, dict):
        return _source_line(project_root, finding.get("path"), line)

    lines = extra.get("lines")
    if isinstance(lines, str):
        first = lines.strip().splitlines()
        candidate = first[0].strip() if first else ""
        if candidate and candidate != "requires login":
            return candidate

    return _source_line(project_root, finding.get("path"), line)


def _source_line(project_root: Path, path_value: object, line: int) -> str:
    if not isinstance(path_value, str) or not path_value:
        return ""

    candidate = Path(path_value)
    if candidate.is_absolute():
        source_path = candidate
    else:
        source_path = project_root / candidate

    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    if line <= 0 or line > len(lines):
        return ""
    return lines[line - 1].strip()


def _attribute_call_expression(code_line: str) -> str | None:
    match = _ATTRIBUTE_CALL_RE.search(code_line)
    if match is None:
        return None
    return f"{match.group('module')}.{match.group('call')}"


def _direct_call_name(code_line: str) -> str:
    match = _DIRECT_CALL_RE.search(code_line)
    if match is None:
        return "subprocess_call"
    return match.group("call")


def main() -> int:
    violations: list[str] = []
    status = "pass"
    summary = "Subprocess boundary allowlist constraints satisfied."

    try:
        violations = _loop_subprocess_boundary_violations(Path("."))
        status = "pass" if not violations else "fail"
        if status == "fail":
            summary = (
                "Detected "
                f"{len(violations)} subprocess invocation(s) outside allowlisted modules."
            )
    except Exception as exc:  # noqa: BLE001
        status = "error"
        summary = f"Semgrep subprocess-boundary scan failed: {exc}"

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=violations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
