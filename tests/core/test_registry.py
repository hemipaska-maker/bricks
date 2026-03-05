"""Tests for bricks.core.registry."""

import pytest

from bricks.core.exceptions import BrickNotFoundError, DuplicateBrickError
from bricks.core.models import BrickMeta
from bricks.core.registry import BrickRegistry


class TestRegister:
    def test_register_and_get_roundtrip(self) -> None:
        reg = BrickRegistry()
        meta = BrickMeta(name="test_brick")

        def my_func() -> None:
            pass

        reg.register("test_brick", my_func, meta)
        func, retrieved_meta = reg.get("test_brick")
        assert func is my_func
        assert retrieved_meta.name == "test_brick"

    def test_duplicate_raises(self) -> None:
        reg = BrickRegistry()
        meta = BrickMeta(name="dup")

        def func() -> None:
            pass

        reg.register("dup", func, meta)
        with pytest.raises(DuplicateBrickError):
            reg.register("dup", func, meta)


class TestGet:
    def test_missing_raises_brick_not_found(self) -> None:
        reg = BrickRegistry()
        with pytest.raises(BrickNotFoundError):
            reg.get("nonexistent")
