import tomllib


class TomlAdapter:
    """TOML format adapter for reading configuration files."""

    def load(self, file_path: str) -> dict:
        """Load TOML configuration from file."""
        with open(file_path, "rb") as f:
            return tomllib.load(f)
