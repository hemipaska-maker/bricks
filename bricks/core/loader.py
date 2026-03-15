"""YAML sequence loader: parses .yaml files into SequenceDefinition models."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bricks.core.exceptions import YamlLoadError
from bricks.core.models import SequenceDefinition


class SequenceLoader:
    """Loads YAML files and parses them into SequenceDefinition instances."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def load_file(self, path: Path) -> SequenceDefinition:
        """Load a SequenceDefinition from a YAML file path.

        Args:
            path: Path to the .yaml file.

        Returns:
            A validated SequenceDefinition.

        Raises:
            YamlLoadError: If the file cannot be parsed or does not conform to schema.
            FileNotFoundError: If the path does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Sequence file not found: {path}")
        try:
            with path.open(encoding="utf-8") as f:
                data = self._yaml.load(f)
        except YAMLError as exc:
            raise YamlLoadError(str(path), exc) from exc
        if data is None:
            raise YamlLoadError(str(path), ValueError("Empty YAML file"))
        return self._parse_raw(data, str(path))

    def load_string(self, content: str) -> SequenceDefinition:
        """Load a SequenceDefinition from a YAML string.

        Args:
            content: YAML content as a string.

        Returns:
            A validated SequenceDefinition.

        Raises:
            YamlLoadError: If the content cannot be parsed.
        """
        try:
            data = self._yaml.load(io.StringIO(content))
        except YAMLError as exc:
            raise YamlLoadError("<string>", exc) from exc
        if data is None:
            raise YamlLoadError("<string>", ValueError("Empty YAML content"))
        return self._parse_raw(data, "<string>")

    def _parse_raw(self, data: Any, source: str) -> SequenceDefinition:
        """Convert raw YAML dict into a validated SequenceDefinition.

        Args:
            data: Raw parsed YAML value (expected to be a dict).
            source: String label for the source (file path or '<string>'), used in
                error messages.

        Returns:
            A validated SequenceDefinition.

        Raises:
            YamlLoadError: If data is not a mapping or fails Pydantic validation.
        """
        if not isinstance(data, dict):
            raise YamlLoadError(source, TypeError(f"Expected mapping, got {type(data).__name__}"))
        try:
            return SequenceDefinition.model_validate(data)
        except ValidationError as exc:
            raise YamlLoadError(source, exc) from exc
