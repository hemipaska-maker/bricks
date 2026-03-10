"""Tests for bricks.core.brick."""

from __future__ import annotations

from typing import Any

import pytest

from bricks.core.brick import BaseBrick, BrickModel, brick
from bricks.core.models import BrickMeta


class TestBrickDecorator:
    def test_decorator_attaches_meta(self) -> None:
        @brick(tags=["test"], description="A test brick")
        def my_brick(x: int) -> int:
            return x

        assert hasattr(my_brick, "__brick_meta__")
        assert my_brick.__brick_meta__.name == "my_brick"  # type: ignore[attr-defined]

    def test_decorator_returns_unwrapped_function(self) -> None:
        @brick()
        def identity(x: int) -> int:
            return x

        assert identity(42) == 42

    def test_decorator_preserves_callable(self) -> None:
        @brick()
        def double(x: int) -> int:
            return x * 2

        assert double(5) == 10

    def test_decorator_with_all_kwargs(self) -> None:
        @brick(tags=["hw"], destructive=True, idempotent=False, description="A test")
        def my_func(x: int) -> int:
            return x

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert meta.tags == ["hw"]
        assert meta.destructive is True
        assert meta.idempotent is False
        assert meta.description == "A test"

    def test_decorator_defaults(self) -> None:
        @brick()
        def my_func() -> None:
            pass

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert meta.tags == []
        assert meta.destructive is False
        assert meta.idempotent is True

    def test_decorator_uses_docstring_as_description(self) -> None:
        @brick()
        def my_func() -> None:
            """This is the docstring."""

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert "docstring" in meta.description

    def test_decorator_name_matches_function(self) -> None:
        @brick()
        def compute_value(x: int) -> int:
            return x

        assert compute_value.__brick_meta__.name == "compute_value"  # type: ignore[attr-defined]

    def test_decorator_empty_description_falls_back_to_docstring(self) -> None:
        @brick(description="")
        def my_func() -> None:
            """Fallback doc."""

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert "Fallback doc" in meta.description

    def test_decorator_explicit_description_overrides_docstring(self) -> None:
        @brick(description="Explicit desc")
        def my_func() -> None:
            """Docstring."""

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert meta.description == "Explicit desc"

    def test_decorator_multiple_tags(self) -> None:
        @brick(tags=["tag1", "tag2", "tag3"])
        def my_func() -> None:
            pass

        meta = my_func.__brick_meta__  # type: ignore[attr-defined]
        assert meta.tags == ["tag1", "tag2", "tag3"]


class TestBrickModel:
    def test_subclass_validates(self) -> None:
        class MyInput(BrickModel):
            channel: int

        inp = MyInput(channel=3)
        assert inp.channel == 3

    def test_brick_model_is_pydantic(self) -> None:
        from pydantic import BaseModel

        assert issubclass(BrickModel, BaseModel)

    def test_brick_model_subclass_validates_with_defaults(self) -> None:
        class MyInput(BrickModel):
            x: int
            y: float = 1.0

        inp = MyInput(x=5)
        assert inp.x == 5
        assert inp.y == 1.0

    def test_brick_model_rejects_wrong_type(self) -> None:
        from pydantic import ValidationError

        class MyInput(BrickModel):
            x: int

        with pytest.raises(ValidationError):
            MyInput(x="not_an_int")  # type: ignore[arg-type]


class TestBaseBrick:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseBrick()  # type: ignore[abstract]

    def test_concrete_subclass_can_instantiate(self) -> None:
        class ConcreteBrick(BaseBrick):
            def execute(
                self, inputs: BrickModel, metadata: BrickMeta
            ) -> dict[str, Any]:
                return {}

        b = ConcreteBrick()
        assert b is not None

    def test_default_meta_values(self) -> None:
        assert BaseBrick.Meta.destructive is False
        assert BaseBrick.Meta.idempotent is True

    def test_concrete_subclass_execute_called(self) -> None:
        class AddBrick(BaseBrick):
            def execute(
                self, inputs: BrickModel, metadata: BrickMeta
            ) -> dict[str, Any]:
                return {"result": 42}

        b = AddBrick()
        meta = BrickMeta(name="add")
        result = b.execute(BrickModel(), meta)
        assert result == {"result": 42}

    def test_base_brick_meta_has_tags(self) -> None:
        assert hasattr(BaseBrick.Meta, "tags")
        assert BaseBrick.Meta.tags == []

    def test_base_brick_has_input_output(self) -> None:
        assert issubclass(BaseBrick.Input, BrickModel)
        assert issubclass(BaseBrick.Output, BrickModel)
