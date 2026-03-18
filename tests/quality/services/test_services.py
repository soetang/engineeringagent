import yaml
import tempfile
import os
from developer.quality.services import CheckGateRunner, ValidationService
from developer.orchestrator.models import GatePhase
from developer.config.service import ConfigService


class TestValidationService:
    """Tests for the ValidationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a temporary config file that points to our test checks.yaml
        config_file_path = os.path.join(self.temp_dir, "test_config.toml")
        with open(config_file_path, "w") as f:
            f.write(f"""[quality]
checks_path = "{os.path.join(self.temp_dir, "checks.yaml")}"
""")

        # Create ValidationService with custom config file
        config_service = ConfigService(config_file=config_file_path)
        self.service = ValidationService(config_service=config_service)

    def teardown_method(self):
        """Clean up test fixtures."""
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

        result = self.service.validate_checks_yaml()
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

        result = self.service.validate_checks_yaml()
        assert not result["valid"]
        assert "not found" in result["message"]

    def test_validate_checks_yaml_invalid_format(self):
        """Test validation of invalid checks.yaml format."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump({"invalid": "format"}, f)

        result = self.service.validate_checks_yaml()
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


class TestCheckGateRunner:
    """Tests for the CheckGateRunner service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a temporary config file that points to our test checks.yaml
        config_file_path = os.path.join(self.temp_dir, "test_config.toml")
        with open(config_file_path, "w") as f:
            f.write(f"""[quality]
checks_path = "{os.path.join(self.temp_dir, "checks.yaml")}"
""")

        # Create CheckGateRunner with custom config file
        config_service = ConfigService(config_file=config_file_path)
        self.service = CheckGateRunner(config_service=config_service)

    def teardown_method(self):
        """Clean up test fixtures."""
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

        result = self.service.execute_checks()
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

        result = self.service.execute_checks()
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

        result = self.service.execute_checks()
        assert not result["success"]
        assert len(result["results"]) == 1
        assert "not found" in result["results"][0]["message"]

    def test_check_with_default_phase_matches_iteration_complete(self):
        """Checks without explicit phase execute as iteration-complete."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {
                    "checks": [
                        {
                            "name": "Default phase check",
                            "filepath": "test_checks.yaml",
                        }
                    ]
                },
                f,
            )

        ref_file_path = os.path.join(self.temp_dir, "test_checks.yaml")
        with open(ref_file_path, "w") as f:
            yaml.dump(
                {
                    "name": "test_checks",
                    "filepath": "",
                    "checks": [
                        {"check_type": "command", "command": ["echo", "iter default"]}
                    ],
                },
                f,
            )

        result = self.service.run_checks_for_phase(GatePhase.ITERATION_COMPLETE)

        assert result["success"]
        assert result["total_checks"] == 1
        assert result["passed_checks"] == 1

    def test_phase_filtering_executes_only_matching_checks(self):
        """Run exactly one phase when multiple phases are configured."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {
                    "checks": [
                        {
                            "name": "Mixed checks",
                            "filepath": "mixed_checks.yaml",
                        }
                    ]
                },
                f,
            )

        mixed_file_path = os.path.join(self.temp_dir, "mixed_checks.yaml")
        with open(mixed_file_path, "w") as f:
            yaml.dump(
                {
                    "name": "mixed",
                    "filepath": "",
                    "checks": [
                        {"check_type": "command", "command": ["echo", "iter"]},
                        {
                            "check_type": "command",
                            "phase": "ImplementationComplete",
                            "command": ["echo", "impl"],
                        },
                    ],
                },
                f,
            )

        iter_result = self.service.run_checks_for_phase(GatePhase.ITERATION_COMPLETE)
        impl_result = self.service.run_checks_for_phase(
            GatePhase.IMPLEMENTATION_COMPLETE
        )

        assert iter_result["success"]
        assert iter_result["total_checks"] == 1
        assert impl_result["success"]
        assert impl_result["total_checks"] == 1

    def test_stop_on_first_failure_short_circuits_execution(self):
        """Stop on first failure should avoid executing later checks."""
        checks_yaml_path = os.path.join(self.temp_dir, "checks.yaml")
        with open(checks_yaml_path, "w") as f:
            yaml.dump(
                {
                    "checks": [
                        {
                            "name": "Three checks",
                            "filepath": "three_checks.yaml",
                        }
                    ]
                },
                f,
            )

        three_checks_path = os.path.join(self.temp_dir, "three_checks.yaml")
        with open(three_checks_path, "w") as f:
            yaml.dump(
                {
                    "name": "three_checks",
                    "filepath": "",
                    "checks": [
                        {"check_type": "command", "command": ["false"]},
                        {
                            "check_type": "command",
                            "command": ["echo", "should be skipped"],
                        },
                        {"check_type": "command", "command": ["true"]},
                    ],
                },
                f,
            )

        short_circuit_result = self.service.run_checks_for_phase(
            GatePhase.ITERATION_COMPLETE,
            stop_on_first_failure=True,
        )
        full_result = self.service.run_checks_for_phase(
            GatePhase.ITERATION_COMPLETE,
            stop_on_first_failure=False,
        )

        assert short_circuit_result["total_checks"] == 1
        assert short_circuit_result["failed_checks"] == 1
        assert full_result["total_checks"] == 3
        assert full_result["failed_checks"] == 1

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
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a temporary config file that points to our test checks.yaml
        config_file_path = os.path.join(self.temp_dir, "test_config.toml")
        with open(config_file_path, "w") as f:
            f.write(f"""[quality]
checks_path = "{os.path.join(self.temp_dir, "checks.yaml")}"
""")

        # Create services with custom config file
        config_service = ConfigService(config_file=config_file_path)
        self.validation_service = ValidationService(config_service=config_service)
        self.execution_service = CheckGateRunner(config_service=config_service)

    def teardown_method(self):
        """Clean up test fixtures."""
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
        validation_result = self.validation_service.validate_checks_yaml()
        assert validation_result["valid"]

        # Step 2: Execute
        execution_result = self.execution_service.execute_checks()
        assert execution_result["success"]
        assert execution_result["total_checks"] == 1
        assert execution_result["passed_checks"] == 1


class TestMixedFormatValidation:
    """Tests for mixed format validation (CheckList + CheckType in same file)."""

    def setup_method(self):
        """Set up test fixtures."""
        # TestMixedFormatValidation uses temporary directories, so we'll configure
        # the service dynamically in each test
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

            # Create a config service that points to our test checks.yaml
            config_file_path = os.path.join(temp_dir, "test_config.toml")
            with open(config_file_path, "w") as f:
                f.write(f"""[quality]
checks_path = "{checks_yaml}"
""")

            config_service = ConfigService(config_file=config_file_path)
            test_service = ValidationService(config_service=config_service)

            # Validate the mixed format file
            result = test_service.validate_checks_yaml()

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

            # Create a config service that points to our test checks.yaml
            config_file_path = os.path.join(temp_dir, "test_config.toml")
            with open(config_file_path, "w") as f:
                f.write(f"""[quality]
checks_path = "{checks_yaml}"
""")

            config_service = ConfigService(config_file=config_file_path)
            test_service = ValidationService(config_service=config_service)

            # Validate the nested references
            result = test_service.validate_checks_yaml()

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

            # Create a config service that points to our test checks.yaml
            config_file_path = os.path.join(temp_dir, "test_config.toml")
            with open(config_file_path, "w") as f:
                f.write(f"""[quality]
checks_path = "{checks_yaml}"
""")

            config_service = ConfigService(config_file=config_file_path)
            test_service = ValidationService(config_service=config_service)

            # Should be invalid
            result = test_service.validate_checks_yaml()
            assert not result["valid"]
            assert (
                "Check must have either 'filepath' or 'check_type'" in result["message"]
            )
