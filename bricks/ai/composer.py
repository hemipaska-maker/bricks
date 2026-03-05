"""AI sequence composer: generates YAML sequences from natural language."""

from __future__ import annotations

from bricks.core.models import SequenceDefinition
from bricks.core.registry import BrickRegistry


class SequenceComposer:
    """Generates SequenceDefinitions from natural language intent.

    Uses an external LLM API (user-provided key) to translate natural
    language descriptions into valid YAML sequences.
    """

    def __init__(self, registry: BrickRegistry, api_key: str) -> None:
        self._registry = registry
        self._api_key = api_key

    def compose(self, intent: str) -> SequenceDefinition:
        """Compose a sequence from a natural language description.

        Args:
            intent: Natural language description of the desired sequence.

        Returns:
            A validated SequenceDefinition.

        Raises:
            NotImplementedError: Always, until the AI layer is implemented.
        """
        raise NotImplementedError("AI composition is not yet implemented")
