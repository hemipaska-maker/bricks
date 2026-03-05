"""Tests for bricks.core.validation."""

import pytest

from bricks.core.exceptions import SequenceValidationError
from bricks.core.models import SequenceDefinition, StepDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.validation import SequenceValidator


class TestSequenceValidator:
    def test_missing_brick_fails_validation(self) -> None:
        reg = BrickRegistry()
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="nonexistent")],
        )
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)
