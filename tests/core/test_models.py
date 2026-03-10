"""Tests for bricks.core.models."""

from __future__ import annotations

import pytest

from bricks.core.models import BrickMeta, SequenceDefinition, StepDefinition


class TestBrickMeta:
    def test_defaults(self) -> None:
        meta = BrickMeta(name="test")
        assert meta.tags == []
        assert meta.destructive is False
        assert meta.idempotent is True

    def test_name_required(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BrickMeta()  # type: ignore[call-arg]


class TestStepDefinition:
    def test_minimal_step(self) -> None:
        step = StepDefinition(name="step1", brick="my_brick")
        assert step.params == {}
        assert step.save_as is None

    def test_save_as_can_be_set(self) -> None:
        step = StepDefinition(name="s1", brick="b", save_as="result")
        assert step.save_as == "result"

    def test_params_can_be_set(self) -> None:
        step = StepDefinition(name="s1", brick="b", params={"x": 42})
        assert step.params == {"x": 42}

    def test_brick_name_stored(self) -> None:
        step = StepDefinition(name="s1", brick="my_op")
        assert step.brick == "my_op"

    def test_step_name_stored(self) -> None:
        step = StepDefinition(name="my_step", brick="b")
        assert step.name == "my_step"


class TestSequenceDefinition:
    def test_minimal_sequence(self) -> None:
        seq = SequenceDefinition(name="test_seq")
        assert seq.steps == []
        assert seq.outputs_map == {}

    def test_inputs_default_empty(self) -> None:
        seq = SequenceDefinition(name="test")
        assert seq.inputs == {}

    def test_steps_can_be_added(self) -> None:
        step = StepDefinition(name="s1", brick="b")
        seq = SequenceDefinition(name="test", steps=[step])
        assert len(seq.steps) == 1
        assert seq.steps[0].name == "s1"

    def test_outputs_map_can_be_set(self) -> None:
        seq = SequenceDefinition(name="test", outputs_map={"result": "${val}"})
        assert seq.outputs_map == {"result": "${val}"}

    def test_description_default_empty(self) -> None:
        seq = SequenceDefinition(name="test")
        assert seq.description == ""

    def test_description_can_be_set(self) -> None:
        seq = SequenceDefinition(name="test", description="My sequence")
        assert seq.description == "My sequence"

    def test_name_required(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SequenceDefinition()  # type: ignore[call-arg]


class TestBrickMetaDefaults:
    def test_tags_default_empty(self) -> None:
        meta = BrickMeta(name="my_brick")
        assert meta.tags == []

    def test_destructive_default_false(self) -> None:
        meta = BrickMeta(name="my_brick")
        assert meta.destructive is False

    def test_idempotent_default_true(self) -> None:
        meta = BrickMeta(name="my_brick")
        assert meta.idempotent is True

    def test_description_default_empty(self) -> None:
        meta = BrickMeta(name="my_brick")
        assert meta.description == ""

    def test_tags_can_be_set(self) -> None:
        meta = BrickMeta(name="my_brick", tags=["math", "io"])
        assert meta.tags == ["math", "io"]

    def test_destructive_can_be_true(self) -> None:
        meta = BrickMeta(name="my_brick", destructive=True)
        assert meta.destructive is True

    def test_idempotent_can_be_false(self) -> None:
        meta = BrickMeta(name="my_brick", idempotent=False)
        assert meta.idempotent is False
