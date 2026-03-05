"""Tests for bricks.core.exceptions."""

from bricks.core.exceptions import (
    BrickError,
    BrickNotFoundError,
    DuplicateBrickError,
    SequenceValidationError,
    VariableResolutionError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_brick_error(self) -> None:
        assert issubclass(DuplicateBrickError, BrickError)
        assert issubclass(BrickNotFoundError, BrickError)
        assert issubclass(SequenceValidationError, BrickError)
        assert issubclass(VariableResolutionError, BrickError)

    def test_duplicate_carries_name(self) -> None:
        err = DuplicateBrickError("my_brick")
        assert err.name == "my_brick"
