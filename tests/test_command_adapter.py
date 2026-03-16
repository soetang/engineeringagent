from typing import List
from pydantic import BaseModel
import pytest
from developer.quality.adapters import CommandAdapter, CommandCheck
from developer.quality.protocol import CheckStatus


def test_command_adapter_success():
    """Test that the command adapter can run successful commands."""
    adapter = CommandAdapter()

    # Test a simple echo command
    checks: List[BaseModel] = [
        CommandCheck(check_type="command", command=["echo", "Hello World"])
    ]

    results = adapter.run_check(checks)

    assert len(results.results) == 1
    assert results.results[0].status == CheckStatus.PASSED
    assert "Hello World" in results.results[0].message


def test_command_adapter_failure():
    """Test that the command adapter handles failing commands."""
    adapter = CommandAdapter()

    # Test a command that should fail
    checks: List[BaseModel] = [CommandCheck(check_type="command", command=["false"])]

    results = adapter.run_check(checks)

    assert len(results.results) == 1
    assert results.results[0].status == CheckStatus.FAILED


def test_command_adapter_multiple():
    """Test that the command adapter can handle multiple commands."""
    adapter = CommandAdapter()

    checks: List[BaseModel] = [
        CommandCheck(check_type="command", command=["echo", "First"]),
        CommandCheck(check_type="command", command=["echo", "Second"]),
        CommandCheck(check_type="command", command=["false"]),
    ]

    results = adapter.run_check(checks)

    assert len(results.results) == 3
    assert results.results[0].status == CheckStatus.PASSED
    assert results.results[1].status == CheckStatus.PASSED
    assert results.results[2].status == CheckStatus.FAILED


def test_command_adapter_execution_error():
    """Test that the command adapter raises exceptions for execution errors."""
    adapter = CommandAdapter()

    # Test with non-existent command
    checks: List[BaseModel] = [
        CommandCheck(check_type="command", command=["nonexistentcommand12345"])
    ]

    with pytest.raises(Exception) as exc_info:
        adapter.run_check(checks)

    assert "Command not found" in str(exc_info.value)


def test_command_adapter_get_check_type():
    """Test that the adapter returns the correct check type."""
    adapter = CommandAdapter()

    check_type = adapter.get_check_type()

    assert check_type == CommandCheck
