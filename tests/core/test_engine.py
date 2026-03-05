"""Tests for bricks.core.engine."""

from bricks.core.engine import SequenceEngine
from bricks.core.registry import BrickRegistry


class TestSequenceEngine:
    def test_engine_creation(self) -> None:
        reg = BrickRegistry()
        engine = SequenceEngine(registry=reg)
        assert engine is not None
