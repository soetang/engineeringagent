from enum import Enum
from typing import List, Protocol, Type
from pydantic import BaseModel


class CheckStatus(Enum):
    """Enum representing the status of a check."""

    PASSED = "passed"
    FAILED = "failed"


class CheckResult(BaseModel):
    """Represents the result of a single check."""

    name: str
    status: CheckStatus
    message: str = ""


class CheckResultList(BaseModel):
    """Represents a list of check results."""

    results: List[CheckResult]


class CheckAdapter(Protocol):
    """Protocol that all check adapters must implement."""

    def run_check(self, checks) -> CheckResultList:
        """
        Run the check and return the results.

        Returns:
            CheckResultList: A list of check results.
        """
        ...

    def get_check_type(self) -> Type[BaseModel]:
        """
        Return the pydantic model representing the check type.

        Returns:
            Type[BaseModel]: The pydantic model for the check type.
        """
        ...
