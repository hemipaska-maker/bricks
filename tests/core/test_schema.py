"""Tests for bricks.core.schema."""

from __future__ import annotations

import pytest

from bricks.core.brick import brick
from bricks.core.exceptions import BrickNotFoundError
from bricks.core.models import SequenceDefinition, StepDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.schema import brick_schema, registry_schema, sequence_schema


def _make_reg() -> BrickRegistry:
    """Create a registry with an 'add' brick for testing."""
    reg = BrickRegistry()

    @brick(tags=["math"], description="Add two numbers", destructive=False)
    def add(a: int, b: int) -> int:
        return a + b

    reg.register("add", add, add.__brick_meta__)
    return reg


class TestBrickSchema:
    def test_schema_has_expected_keys(self) -> None:
        """brick_schema returns correct metadata fields."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        assert schema["name"] == "add"
        assert schema["description"] == "Add two numbers"
        assert schema["tags"] == ["math"]
        assert schema["destructive"] is False
        assert "parameters" in schema

    def test_schema_parameters_have_correct_structure(self) -> None:
        """Parameters dict includes correct type and required info."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        params = schema["parameters"]
        assert "a" in params
        assert "b" in params
        assert params["a"]["required"] is True

    def test_schema_raises_for_unknown_brick(self) -> None:
        """BrickNotFoundError raised when brick is not registered."""
        reg = BrickRegistry()
        with pytest.raises(BrickNotFoundError):
            brick_schema("nonexistent", reg)

    def test_schema_idempotent_field(self) -> None:
        """brick_schema includes idempotent field from metadata."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        assert "idempotent" in schema

    def test_schema_parameter_type_annotation(self) -> None:
        """Parameter type annotation is captured as a string."""
        reg = _make_reg()
        schema = brick_schema("add", reg)
        params = schema["parameters"]
        # int annotation should be present as a string form
        assert "int" in params["a"]["type"]


class TestRegistrySchema:
    def test_registry_schema_returns_list(self) -> None:
        """registry_schema returns a list with one entry per brick."""
        reg = _make_reg()
        schemas = registry_schema(reg)
        assert isinstance(schemas, list)
        assert len(schemas) == 1
        assert schemas[0]["name"] == "add"

    def test_empty_registry_returns_empty_list(self) -> None:
        """registry_schema returns empty list for empty registry."""
        reg = BrickRegistry()
        assert registry_schema(reg) == []

    def test_registry_schema_sorted_by_name(self) -> None:
        """registry_schema results are sorted alphabetically by brick name."""
        reg = BrickRegistry()

        @brick(description="Zebra")
        def zebra_brick(x: int) -> int:
            return x

        @brick(description="Alpha")
        def alpha_brick(x: int) -> int:
            return x

        reg.register("zebra_brick", zebra_brick, zebra_brick.__brick_meta__)
        reg.register("alpha_brick", alpha_brick, alpha_brick.__brick_meta__)

        schemas = registry_schema(reg)
        assert schemas[0]["name"] == "alpha_brick"
        assert schemas[1]["name"] == "zebra_brick"


class TestSequenceSchema:
    def test_sequence_schema_has_expected_keys(self) -> None:
        """sequence_schema returns correct top-level keys."""
        seq = SequenceDefinition(
            name="my_seq",
            description="A test sequence",
            inputs={"x": "int"},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="add",
                    params={"a": "${inputs.x}", "b": 1},
                )
            ],
            outputs_map={"result": "${s1}"},
        )
        schema = sequence_schema(seq)
        assert schema["name"] == "my_seq"
        assert schema["description"] == "A test sequence"
        assert schema["inputs"] == {"x": "int"}
        assert len(schema["steps"]) == 1
        assert schema["steps"][0]["name"] == "s1"
        assert schema["outputs_map"] == {"result": "${s1}"}

    def test_sequence_schema_step_fields(self) -> None:
        """sequence_schema step entries include all required step fields."""
        seq = SequenceDefinition(
            name="test_seq",
            steps=[
                StepDefinition(
                    name="step1",
                    brick="some_brick",
                    params={"key": "value"},
                    save_as="step1_result",
                )
            ],
        )
        schema = sequence_schema(seq)
        step = schema["steps"][0]
        assert step["name"] == "step1"
        assert step["brick"] == "some_brick"
        assert step["params"] == {"key": "value"}
        assert step["save_as"] == "step1_result"

    def test_sequence_schema_empty_sequence(self) -> None:
        """sequence_schema works with a sequence that has no steps."""
        seq = SequenceDefinition(name="empty_seq")
        schema = sequence_schema(seq)
        assert schema["name"] == "empty_seq"
        assert schema["steps"] == []
        assert schema["inputs"] == {}
        assert schema["outputs_map"] == {}
