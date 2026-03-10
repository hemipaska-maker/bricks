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


class TestRegistryListAndHas:
    def test_list_all_sorted(self) -> None:
        reg = BrickRegistry()
        reg.register("zebra", lambda: None, BrickMeta(name="zebra"))  # noqa: E731
        reg.register("apple", lambda: None, BrickMeta(name="apple"))  # noqa: E731
        names = [name for name, _ in reg.list_all()]
        assert names == ["apple", "zebra"]

    def test_list_all_empty(self) -> None:
        reg = BrickRegistry()
        assert reg.list_all() == []

    def test_has_returns_false_for_unknown(self) -> None:
        reg = BrickRegistry()
        assert reg.has("nonexistent") is False

    def test_has_returns_true_after_register(self) -> None:
        reg = BrickRegistry()
        reg.register("my_brick", lambda: None, BrickMeta(name="my_brick"))  # noqa: E731
        assert reg.has("my_brick") is True

    def test_clear_empties_registry(self) -> None:
        reg = BrickRegistry()
        reg.register("b1", lambda: None, BrickMeta(name="b1"))  # noqa: E731
        reg.clear()
        assert reg.list_all() == []
        assert reg.has("b1") is False

    def test_get_raises_for_unknown(self) -> None:
        reg = BrickRegistry()
        with pytest.raises(BrickNotFoundError):
            reg.get("missing")

    def test_multiple_bricks_retrieved_correctly(self) -> None:
        reg = BrickRegistry()

        def fn_a() -> str:
            return "a"

        def fn_b() -> str:
            return "b"

        reg.register("a", fn_a, BrickMeta(name="a"))
        reg.register("b", fn_b, BrickMeta(name="b"))
        callable_a, meta_a = reg.get("a")
        callable_b, meta_b = reg.get("b")
        assert callable_a() == "a"
        assert callable_b() == "b"
        assert meta_a.name == "a"
        assert meta_b.name == "b"

    def test_list_all_returns_name_meta_tuples(self) -> None:
        reg = BrickRegistry()
        meta = BrickMeta(name="my_brick", tags=["test"])
        reg.register("my_brick", lambda: None, meta)  # noqa: E731
        result = reg.list_all()
        assert len(result) == 1
        name, retrieved_meta = result[0]
        assert name == "my_brick"
        assert retrieved_meta.tags == ["test"]

    def test_register_many_and_list_all_sorted(self) -> None:
        reg = BrickRegistry()
        names = ["charlie", "alpha", "beta", "delta"]
        for n in names:
            reg.register(n, lambda: None, BrickMeta(name=n))  # noqa: E731
        listed_names = [name for name, _ in reg.list_all()]
        assert listed_names == sorted(names)
