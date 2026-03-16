# Adapters package for quality checks
# This package contains adapters for various quality check commands

from .command_adapter import CommandAdapter, CommandCheck
from .agentic_review_adapter import AgenticReviewAdapter, AgenticReviewCheck

__all__ = [
    "CommandAdapter",
    "CommandCheck",
    "AgenticReviewAdapter",
    "AgenticReviewCheck",
    "get_adapters",
]


def get_adapters():
    """Returns a list of available adapters with their check types.

    Returns:
        List of dicts with structure:
        [
            {
                "check_type": "command",  # The check_type identifier
                "adapter": CommandAdapter()  # The adapter instance
            },
            # ... more adapters
        ]
    """
    return [
        {"check_type": "command", "adapter": CommandAdapter()},
        {"check_type": "agentic_review", "adapter": AgenticReviewAdapter()},
        # Add more adapters here manually
    ]
