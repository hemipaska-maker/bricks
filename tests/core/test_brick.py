"""Tests for bricks.core.brick."""

from bricks.core.brick import BrickModel, brick


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


class TestBrickModel:
    def test_subclass_validates(self) -> None:
        class MyInput(BrickModel):
            channel: int

        inp = MyInput(channel=3)
        assert inp.channel == 3
