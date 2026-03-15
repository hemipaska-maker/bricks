"""Brick definitions: @brick decorator, BaseBrick class, and BrickModel base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar, Protocol, cast, runtime_checkable

from pydantic import BaseModel

from bricks.core.models import BrickMeta


class BrickModel(BaseModel):
    """Base Pydantic model for Brick Input/Output schemas.

    All Brick inputs and outputs should subclass this.
    Provides Pydantic v2 validation and serialization.
    """


@runtime_checkable
class BrickFunction(Protocol):
    """Protocol for callables decorated with ``@brick``.

    Guarantees the presence of ``__brick_meta__`` so that type checkers
    can verify access to metadata without ``# type: ignore`` suppression.
    """

    __brick_meta__: BrickMeta

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the brick function."""
        ...


class BaseBrick(ABC):
    """Abstract base class for class-based Bricks.

    Subclasses must define inner classes Meta, Input, Output
    and implement the execute() method.

    Example::

        class ReadTemperature(BaseBrick):
            class Meta:
                tags = ["hardware"]
                destructive = False

            class Input(BrickModel):
                channel: int

            class Output(BrickModel):
                temperature: float

            def execute(
                self, inputs: BrickModel, metadata: BrickMeta,
            ) -> dict[str, Any]:
                ...
    """

    class Meta:
        """Brick metadata. Subclasses should override."""

        tags: ClassVar[list[str]] = []
        destructive: bool = False
        idempotent: bool = True
        description: str = ""

    class Input(BrickModel):
        """Default empty input schema. Override in subclasses."""

    class Output(BrickModel):
        """Default empty output schema. Override in subclasses."""

    @abstractmethod
    def execute(self, inputs: BrickModel, metadata: BrickMeta) -> dict[str, Any]:
        """Execute the brick logic.

        Args:
            inputs: Validated input data.
            metadata: Execution metadata (sequence name, step index, etc.).

        Returns:
            Dictionary matching the Output schema fields.
        """
        ...


def brick(
    *,
    tags: list[str] | None = None,
    destructive: bool = False,
    idempotent: bool = True,
    description: str = "",
) -> Callable[[Callable[..., Any]], BrickFunction]:
    """Decorator that registers a function as a Brick.

    Args:
        tags: Classification tags for the brick.
        destructive: Whether the brick modifies external state irreversibly.
        idempotent: Whether repeated execution produces the same result.
        description: Human-readable description.

    Returns:
        The original function, unwrapped, with a ``__brick_meta__`` attribute
        attached. The return type is ``BrickFunction`` so callers can safely
        access ``fn.__brick_meta__`` without type-ignore suppression.

    Example::

        @brick(tags=["hardware"], destructive=False)
        def read_temperature(channel: int) -> float:
            return sensor.read(channel)
    """

    def decorator(func: Callable[..., Any]) -> BrickFunction:
        func.__brick_meta__ = BrickMeta(  # type: ignore[attr-defined]
            name=func.__name__,
            tags=tags or [],
            destructive=destructive,
            idempotent=idempotent,
            description=description or func.__doc__ or "",
        )
        return cast(BrickFunction, func)

    return decorator
