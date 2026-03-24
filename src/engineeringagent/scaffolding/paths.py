"""Shared scaffold path and marker constants."""

DEFAULT_HARNESS_DIR = "harness"
PROMPTS_DIR = "prompts"
QUALITY_DIR = "quality"

CHECKS_FILE_NAME = "checks.yaml"
QUALITY_COMMANDS_FILE_NAME = "commands.yaml"
IMPLEMENTATION_PROMPT_NAME = "implementation_prompt.md"
COMMIT_MESSAGE_PROMPT_NAME = "commit_message_prompt.md"
PULL_REQUEST_PROMPT_NAME = "pull_request_prompt.md"

AGENTS_MD_START_MARKER = "<!-- engineeringagent:init:start -->"
AGENTS_MD_END_MARKER = "<!-- engineeringagent:init:end -->"


def build_prompt_path(harness_dir: str, prompt_name: str) -> str:
    """Build a relative path to a scaffolded prompt file."""
    return f"{harness_dir}/{PROMPTS_DIR}/{prompt_name}"


def build_checks_path(harness_dir: str) -> str:
    """Build a relative path to the main checks file."""
    return f"{harness_dir}/{CHECKS_FILE_NAME}"
