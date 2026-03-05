"""Tests for bricks.core.models."""

from bricks.core.models import BrickMeta, SequenceDefinition, StepDefinition


class TestBrickMeta:
    def test_defaults(self) -> None:
        meta = BrickMeta(name="test")
        assert meta.tags == []
        assert meta.destructive is False
        assert meta.idempotent is True


class TestStepDefinition:
    def test_minimal_step(self) -> None:
        step = StepDefinition(name="step1", brick="my_brick")
        assert step.params == {}
        assert step.save_as is None


class TestSequenceDefinition:
    def test_minimal_sequence(self) -> None:
        seq = SequenceDefinition(name="test_seq")
        assert seq.steps == []
        assert seq.outputs_map == {}
