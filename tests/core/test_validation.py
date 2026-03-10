"""Tests for bricks.core.validation."""

from __future__ import annotations

import pytest

from bricks.core.exceptions import SequenceValidationError
from bricks.core.models import BrickMeta, SequenceDefinition, StepDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.validation import SequenceValidator


def _make_registry(*brick_names: str) -> BrickRegistry:
    """Create a BrickRegistry with the given brick names registered."""
    reg = BrickRegistry()
    for name in brick_names:
        reg.register(name, lambda: None, BrickMeta(name=name))
    return reg


class TestCheck1MissingBrick:
    def test_missing_brick_fails_validation(self) -> None:
        reg = BrickRegistry()
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="nonexistent")],
        )
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)

    def test_present_brick_passes(self) -> None:
        reg = _make_registry("my_brick")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="my_brick")],
        )
        result = validator.validate(seq)
        assert result == []


class TestCheck2SaveAsUniqueness:
    def test_duplicate_save_as_fails(self) -> None:
        reg = _make_registry("brick_a", "brick_b")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(name="s1", brick="brick_a", save_as="result"),
                StepDefinition(name="s2", brick="brick_b", save_as="result"),
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("result" in e for e in exc_info.value.errors)

    def test_unique_save_as_passes(self) -> None:
        reg = _make_registry("brick_a", "brick_b")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(name="s1", brick="brick_a", save_as="result1"),
                StepDefinition(name="s2", brick="brick_b", save_as="result2"),
            ],
        )
        result = validator.validate(seq)
        assert result == []


class TestCheck3DuplicateStepNames:
    def test_duplicate_step_name_fails(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(name="s1", brick="brick_a"),
                StepDefinition(name="s1", brick="brick_a"),
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("Duplicate step name" in e for e in exc_info.value.errors)

    def test_unique_step_names_pass(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(name="s1", brick="brick_a"),
                StepDefinition(name="s2", brick="brick_a"),
            ],
        )
        result = validator.validate(seq)
        assert result == []


class TestCheck4OutputsMapReferences:
    def test_outputs_map_undefined_reference_fails(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="brick_a", save_as="val")],
            outputs_map={"out": "${nonexistent}"},
        )
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)

    def test_outputs_map_valid_save_as_passes(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="brick_a", save_as="val")],
            outputs_map={"out": "${val}"},
        )
        result = validator.validate(seq)
        assert result == []

    def test_outputs_map_valid_input_ref_passes(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={"x": "int"},
            steps=[StepDefinition(name="s1", brick="brick_a")],
            outputs_map={"out": "${inputs.x}"},
        )
        result = validator.validate(seq)
        assert result == []


class TestCheck5InputReferences:
    def test_undeclared_input_ref_fails(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={"x": "int"},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"val": "${inputs.y}"},
                )
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("y" in e for e in exc_info.value.errors)

    def test_declared_input_ref_passes(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={"x": "int"},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"val": "${inputs.x}"},
                )
            ],
        )
        result = validator.validate(seq)
        assert result == []

    def test_nested_dict_params_checked(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"nested": {"key": "${inputs.missing}"}},
                )
            ],
        )
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)

    def test_nested_list_params_checked(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"items": ["${inputs.missing}"]},
                )
            ],
        )
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)


class TestCheck6ResultReferences:
    def test_forward_reference_fails(self) -> None:
        reg = _make_registry("brick_a", "brick_b")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"val": "${future_result}"},
                ),
                StepDefinition(
                    name="s2",
                    brick="brick_b",
                    save_as="future_result",
                ),
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("not yet available" in e for e in exc_info.value.errors)

    def test_undefined_variable_fails(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"val": "${totally_undefined}"},
                )
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("undefined variable" in e for e in exc_info.value.errors)

    def test_valid_backward_reference_passes(self) -> None:
        reg = _make_registry("brick_a", "brick_b")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(name="s1", brick="brick_a", save_as="first"),
                StepDefinition(
                    name="s2",
                    brick="brick_b",
                    params={"val": "${first}"},
                ),
            ],
        )
        result = validator.validate(seq)
        assert result == []

    def test_multiple_errors_collected(self) -> None:
        reg = _make_registry("brick_a")
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1",
                    brick="brick_a",
                    params={"a": "${inputs.missing}", "b": "${undefined}"},
                )
            ],
        )
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        err = exc_info.value
        assert len(err.errors) >= 2


class TestCheck7EmptySequence:
    def test_empty_sequence_fails(self) -> None:
        reg = BrickRegistry()
        validator = SequenceValidator(registry=reg)
        seq = SequenceDefinition(name="empty")
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        assert any("no steps" in e for e in exc_info.value.errors)
