import yaml
import tempfile
import os
from developer.quality.services import ValidationService, ExecutionService


class TestValidationService:
    """Tests for the ValidationService."""

    def setup_method(self):
        self.service = ValidationService()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_validate_checks_yaml_valid(self):
        """Test validation of a valid checks.yaml file."""
        # Create a valid checks.yaml
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {"checks": [{"name": "Test Checks", "filepath": "test_checks.yaml"}]}, f
            )

        # Create a valid referenced file
        ref_file_path = os.path.join(self.temp_dir, "test_checks.yaml")
        with open(ref_file_path, "w") as f:
            yaml.dump({"name": "test_checks", "filepath": "", "checks": []}, f)

        result = self.service.validate_checks_yaml(checks_yaml_path)
        assert result["valid"]
        assert len(result["checks"]) == 1
        assert result["checks"][0]["name"] == "Test Checks"

    def test_validate_checks_yaml_missing_file(self):
        """Test validation when referenced file is missing."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {"checks": [{"name": "Test Checks", "filepath": "nonexistent.yaml"}]}, f
            )

        result = self.service.validate_checks_yaml(checks_yaml_path)
        assert not result["valid"]
        assert "not found" in result["message"]

    def test_validate_checks_yaml_invalid_format(self):
        """Test validation of invalid checks.yaml format."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump({"invalid": "format"}, f)

        result = self.service.validate_checks_yaml(checks_yaml_path)
        assert not result["valid"]
        assert "missing 'checks' section" in result["message"]

    def test_validate_quality_spec_valid(self):
        """Test validation of a valid quality specification."""
        spec = {"name": "test_spec", "filepath": "", "checks": []}

        result = self.service.validate_quality_spec(spec)
        assert result["valid"]

    def test_validate_quality_spec_invalid(self):
        """Test validation of an invalid quality specification."""
        spec = {
            "name": "test_spec",
            # Missing required 'filepath' and 'checks' fields
        }

        result = self.service.validate_quality_spec(spec)
        assert not result["valid"]


class TestExecutionService:
    """Tests for the ExecutionService."""

    def setup_method(self):
        self.service = ExecutionService()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_execute_checks_valid(self):
        """Test execution of valid checks."""
        # Create a valid checks.yaml
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {
                    "checks": [
                        {
                            "name": "Test Checks",
                            "filepath": os.path.join(self.temp_dir, "test_checks.yaml"),
                        }
                    ]
                },
                f,
            )

        # Create a valid referenced file with passing command
        ref_file_path = os.path.join(self.temp_dir, "test_checks.yaml")
        with open(ref_file_path, "w") as f:
            yaml.dump(
                {
                    "name": "test_checks",
                    "filepath": "",
                    "checks": [{"check_type": "command", "command": ["echo", "test"]}],
                },
                f,
            )

        result = self.service.execute_checks(checks_yaml_path)
        assert result["success"]
        assert result["total_checks"] == 1
        assert result["passed_checks"] == 1
        assert result["failed_checks"] == 0

    def test_execute_checks_failing_command(self):
        """Test execution with a failing command."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {"checks": [{"name": "Test Checks", "filepath": "test_checks.yaml"}]}, f
            )

        ref_file_path = os.path.join(self.temp_dir, "test_checks.yaml")
        with open(ref_file_path, "w") as f:
            yaml.dump(
                {
                    "name": "test_checks",
                    "filepath": "",
                    "checks": [
                        {
                            "check_type": "command",
                            "command": ["false"],  # This command always fails
                        }
                    ],
                },
                f,
            )

        result = self.service.execute_checks(checks_yaml_path)
        assert not result["success"]
        assert result["total_checks"] == 1
        assert result["passed_checks"] == 0
        assert result["failed_checks"] == 1

    def test_execute_checks_missing_file(self):
        """Test execution when referenced file is missing."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {"checks": [{"name": "Test Checks", "filepath": "nonexistent.yaml"}]}, f
            )

        result = self.service.execute_checks(checks_yaml_path)
        assert not result["success"]
        assert len(result["results"]) == 1
        assert "not found" in result["results"][0]["message"]

    def test_execute_single_spec(self):
        """Test execution of a single quality specification."""
        spec = {
            "name": "test_spec",
            "filepath": "",
            "checks": [{"check_type": "command", "command": ["echo", "single test"]}],
        }

        result = self.service.execute_single_spec(spec)
        assert result["success"]
        assert result["total_checks"] == 1
        assert result["passed_checks"] == 1


class TestIntegration:
    """Integration tests for services working together."""

    def setup_method(self):
        self.validation_service = ValidationService()
        self.execution_service = ExecutionService()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_validation_then_execution_workflow(self):
        """Test the complete validation then execution workflow."""
        # Create a valid checks.yaml
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {
                    "checks": [
                        {"name": "Integration Test", "filepath": "integration.yaml"}
                    ]
                },
                f,
            )

        # Create a valid referenced file
        ref_file_path = os.path.join(self.temp_dir, "integration.yaml")
        with open(ref_file_path, "w") as f:
            yaml.dump(
                {
                    "name": "integration",
                    "filepath": "",
                    "checks": [
                        {
                            "check_type": "command",
                            "command": ["echo", "integration test passed"],
                        }
                    ],
                },
                f,
            )

        # Step 1: Validate
        validation_result = self.validation_service.validate_checks_yaml(
            checks_yaml_path
        )
        assert validation_result["valid"]

        # Step 2: Execute
        execution_result = self.execution_service.execute_checks(checks_yaml_path)
        assert execution_result["success"]
        assert execution_result["total_checks"] == 1
        assert execution_result["passed_checks"] == 1


class TestMixedFormatValidation:
    """Tests for mixed format validation (CheckList + CheckType in same file)."""

    def setup_method(self):
        self.service = ValidationService()

    def test_mixed_format_validation(self):
        """Test validation of mixed format with both CheckList and CheckType items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple command file
            command_file = os.path.join(temp_dir, "commands.yaml")
            with open(command_file, "w") as f:
                f.write("""name: "commands"
filepath: ""
checks:
  - check_type: "command"
    check_category: "linting"
    command: ["echo", "linting"]
""")

            # Create main checks.yaml with mixed format
            checks_yaml = os.path.join(temp_dir, "checks.yaml")
            with open(checks_yaml, "w") as f:
                f.write("""checks:
  - name: "External Commands"
    filepath: "commands.yaml"
  - check_type: "command"
    check_category: "testing"
    command: ["echo", "testing"]
  - name: "Another File"
    filepath: "commands.yaml"
""")

            # Validate the mixed format file
            result = self.service.validate_checks_yaml(checks_yaml)
            
            # Should be valid
            assert result["valid"]
            assert result["message"] == "All 3 check configurations are valid"
            assert len(result["checks"]) == 3
            
            # Check that we have both types
            check_names = [check["name"] for check in result["checks"]]
            assert "External Commands" in check_names
            assert "Another File" in check_names
            assert "command" in check_names  # The direct check

    def test_nested_file_references(self):
        """Test that files can reference other files (nested references)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create base command file
            base_file = os.path.join(temp_dir, "base.yaml")
            with open(base_file, "w") as f:
                f.write("""name: "base"
filepath: ""
checks:
  - check_type: "command"
    command: ["echo", "base"]
""")

            # Create intermediate file that references base file
            intermediate_file = os.path.join(temp_dir, "intermediate.yaml")
            with open(intermediate_file, "w") as f:
                f.write("""name: "intermediate"
filepath: ""
checks:
  - name: "Base Reference"
    filepath: "base.yaml"
  - check_type: "command"
    command: ["echo", "intermediate"]
""")

            # Create main checks.yaml that references intermediate file
            checks_yaml = os.path.join(temp_dir, "checks.yaml")
            with open(checks_yaml, "w") as f:
                f.write("""checks:
  - name: "Intermediate Reference"
    filepath: "intermediate.yaml"
  - check_type: "command"
    command: ["echo", "main"]
""")

            # Validate the nested references
            result = self.service.validate_checks_yaml(checks_yaml)
            
            # Should be valid
            assert result["valid"]
            assert result["message"] == "All 2 check configurations are valid"
            assert len(result["checks"]) == 2

    def test_invalid_mixed_format(self):
        """Test that invalid mixed format items are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a dummy commands.yaml file so it doesn't fail on missing file
            commands_yaml = os.path.join(temp_dir, "commands.yaml")
            with open(commands_yaml, "w") as f:
                f.write("""name: "commands"
filepath: ""
checks:
  - check_type: "command"
    command: ["echo", "test"]
""")

            # Create checks.yaml with invalid item (missing both filepath and check_type)
            checks_yaml = os.path.join(temp_dir, "checks.yaml")
            with open(checks_yaml, "w") as f:
                f.write("""checks:
  - name: "Valid Check"
    filepath: "commands.yaml"
  - name: "Invalid Check"
    invalid_field: "value"
""")

            # Should be invalid
            result = self.service.validate_checks_yaml(checks_yaml)
            assert not result["valid"]
            assert "Check must have either 'filepath' or 'check_type'" in result["message"]
