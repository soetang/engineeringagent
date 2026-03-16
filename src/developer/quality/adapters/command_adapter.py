from typing import List
from pydantic import BaseModel, Field
from subprocess import run, CompletedProcess
from ..protocol import CheckAdapter, CheckResult, CheckResultList, CheckStatus
from ..models import CheckType


class CommandCheck(CheckType):
    """Represents a terminal command check."""

    command: List[str] = Field(..., description="Command and arguments to run")

    def __init__(self, **data):
        # Set default check_type to "command" if not provided
        if "check_type" not in data:
            data["check_type"] = "command"
        super().__init__(**data)


class CommandAdapter(CheckAdapter):
    """Adapter for running terminal commands as quality checks."""

    def run_check(self, checks: List[BaseModel]) -> CheckResultList:
        """Run the command checks and return the results."""
        results = []

        for check in checks:
            # Accept both CommandCheck from adapter and raw dicts with command checks
            if isinstance(check, CommandCheck):
                command_check = check
                command_list = command_check.command
            elif (
                isinstance(check, dict)
                and check.get("check_type") == "command"
                and "command" in check
            ):
                # Handle raw dict command checks
                command_check = check
                command_list = check["command"]
            else:
                continue

            try:
                # Run the command
                result: CompletedProcess = run(
                    command_list, capture_output=True, text=True
                )

                if result.returncode == 0:
                    status = CheckStatus.PASSED
                    message = (
                        result.stdout
                        if result.stdout
                        else "Command executed successfully"
                    )
                else:
                    # Command ran but failed - this is expected behavior for quality checks
                    status = CheckStatus.FAILED
                    message = (
                        result.stderr
                        if result.stderr
                        else f"Command failed with return code {result.returncode}"
                    )

                results.append(
                    CheckResult(
                        name=" ".join(command_list), status=status, message=message
                    )
                )

            except FileNotFoundError as e:
                # Command not found - this is an execution error, not a check failure
                raise Exception(
                    f"Command not found: {' '.join(command_list)} - {str(e)}"
                )
            except PermissionError as e:
                # Permission error - this is an execution error
                raise Exception(
                    f"Permission denied executing command: {' '.join(command_list)} - {str(e)}"
                )
            except Exception as e:
                # Other execution errors
                raise Exception(
                    f"Error executing command: {' '.join(command_list)} - {str(e)}"
                )

        return CheckResultList(results=results)

    def get_check_type(self) -> type[BaseModel]:
        """Return the pydantic model representing the check type."""
        return CommandCheck
