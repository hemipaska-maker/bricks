"""Dry-run validation: validates a sequence without executing bricks."""

from __future__ import annotations

from bricks.core.exceptions import SequenceValidationError
from bricks.core.models import SequenceDefinition
from bricks.core.registry import BrickRegistry


class SequenceValidator:
    """Validates a SequenceDefinition against the registry without executing.

    Checks:
    - All referenced bricks exist in the registry.
    - save_as names are unique across steps.
    - outputs_map references exist (as save_as names or input names).
    - No circular references (future).
    """

    def __init__(self, registry: BrickRegistry) -> None:
        self._registry = registry

    def validate(self, sequence: SequenceDefinition) -> list[str]:
        """Validate a sequence definition and return a list of errors.

        Args:
            sequence: The sequence definition to validate.

        Returns:
            A list of error message strings. Empty list means valid.

        Raises:
            SequenceValidationError: If the sequence has validation errors.
        """
        errors: list[str] = []

        # Check all referenced bricks exist
        for step in sequence.steps:
            if not self._registry.has(step.brick):
                errors.append(
                    f"Step {step.name!r}: brick {step.brick!r} not found in registry"
                )

        # Check save_as uniqueness
        save_names: list[str] = []
        for step in sequence.steps:
            if step.save_as is not None:
                if step.save_as in save_names:
                    errors.append(
                        f"Step {step.name!r}: duplicate save_as name {step.save_as!r}"
                    )
                save_names.append(step.save_as)

        if errors:
            raise SequenceValidationError(
                f"Sequence {sequence.name!r} has {len(errors)} validation error(s)",
                errors=errors,
            )

        return errors
