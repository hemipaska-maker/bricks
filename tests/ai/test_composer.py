"""Tests for bricks.ai.composer."""

import pytest

from bricks.ai.composer import SequenceComposer
from bricks.core.registry import BrickRegistry


class TestSequenceComposer:
    def test_compose_raises_not_implemented(self) -> None:
        reg = BrickRegistry()
        composer = SequenceComposer(registry=reg, api_key="test-key")
        with pytest.raises(NotImplementedError):
            composer.compose("do something")
