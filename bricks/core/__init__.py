"""Bricks core: engine, context, validation, and Brick base classes."""

from bricks.core.brick import BaseBrick, BrickModel, brick
from bricks.core.context import ExecutionContext
from bricks.core.engine import SequenceEngine
from bricks.core.exceptions import (
    BrickError,
    BrickExecutionError,
    BrickNotFoundError,
    DuplicateBrickError,
    SequenceValidationError,
    VariableResolutionError,
)
from bricks.core.models import BrickMeta, SequenceDefinition, StepDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.resolver import ReferenceResolver
from bricks.core.validation import SequenceValidator

__all__ = [
    "BaseBrick",
    "BrickError",
    "BrickExecutionError",
    "BrickMeta",
    "BrickModel",
    "BrickNotFoundError",
    "BrickRegistry",
    "DuplicateBrickError",
    "ExecutionContext",
    "ReferenceResolver",
    "SequenceDefinition",
    "SequenceEngine",
    "SequenceValidationError",
    "SequenceValidator",
    "StepDefinition",
    "VariableResolutionError",
    "brick",
]
