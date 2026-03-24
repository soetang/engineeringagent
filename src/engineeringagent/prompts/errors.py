"""Prompt-related errors for template loading and rendering."""


class PromptTemplateError(RuntimeError):
    """Base error raised by prompt template operations."""


class PromptTemplateMissingError(PromptTemplateError):
    """Raised when the configured prompt template file cannot be found."""


class PromptTemplateSyntaxError(PromptTemplateError):
    """Raised when a prompt template cannot be parsed."""
