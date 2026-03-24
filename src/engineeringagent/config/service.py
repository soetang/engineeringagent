from typing import Type, TypeVar
from pydantic import BaseModel
from .adapter.toml_adapter import TomlAdapter

T = TypeVar("T", bound=BaseModel)


class ConfigService:
    """Completely agnostic configuration service - domains pass models."""

    def __init__(self, config_file: str = "engineeringagent.toml"):
        """Initialize with the configuration file to use."""
        self._config_file = config_file
        self._adapter = TomlAdapter()
        self._cache: dict[str, BaseModel] = {}

    def get_config(self, section: str, model: Type[T]) -> T:
        """Get configuration for any section using any model - completely agnostic."""
        cache_key = f"{self._config_file}:{section}"

        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[return-value]

        raw_data = self._adapter.load(self._config_file)
        section_data = raw_data.get(section, {})

        # Parse with the model provided by the domain
        config_instance = model(**section_data)
        self._cache[cache_key] = config_instance

        return config_instance  # type: ignore[return-value]

    def has_section(self, section: str) -> bool:
        """Return whether the loaded configuration file declares a section."""
        raw_data = self._adapter.load(self._config_file)
        return section in raw_data

    def clear_cache(self):
        """Clear the configuration cache."""
        self._cache.clear()
