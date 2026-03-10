"""Tests for bricks.core.resolver."""

import pytest

from bricks.core.context import ExecutionContext
from bricks.core.exceptions import VariableResolutionError
from bricks.core.resolver import ReferenceResolver


class TestReferenceResolver:
    def test_resolve_simple_reference(self) -> None:
        ctx = ExecutionContext(inputs={"channel": 3})
        resolver = ReferenceResolver()
        result = resolver.resolve("${inputs.channel}", ctx)
        assert result == 3

    def test_unresolvable_raises(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        with pytest.raises(VariableResolutionError):
            resolver.resolve("${missing.var}", ctx)


class TestResolverEdgeCases:
    def test_plain_string_unchanged(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        assert resolver.resolve("hello world", ctx) == "hello world"

    def test_integer_unchanged(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        assert resolver.resolve(42, ctx) == 42

    def test_float_unchanged(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        assert resolver.resolve(3.14, ctx) == 3.14

    def test_bool_unchanged(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        assert resolver.resolve(True, ctx) is True

    def test_none_unchanged(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        assert resolver.resolve(None, ctx) is None

    def test_embedded_ref_in_string(self) -> None:
        ctx = ExecutionContext(inputs={"name": "Alice"})
        resolver = ReferenceResolver()
        result = resolver.resolve("Hello, ${inputs.name}!", ctx)
        assert result == "Hello, Alice!"

    def test_multiple_refs_in_string(self) -> None:
        ctx = ExecutionContext(inputs={"a": "foo", "b": "bar"})
        resolver = ReferenceResolver()
        result = resolver.resolve("${inputs.a} and ${inputs.b}", ctx)
        assert result == "foo and bar"

    def test_nested_dict_resolved(self) -> None:
        ctx = ExecutionContext(inputs={"x": 10})
        resolver = ReferenceResolver()
        result = resolver.resolve({"key": "${inputs.x}", "literal": 5}, ctx)
        assert result == {"key": 10, "literal": 5}

    def test_list_resolved(self) -> None:
        ctx = ExecutionContext(inputs={"val": 99})
        resolver = ReferenceResolver()
        result = resolver.resolve(["${inputs.val}", 1, 2], ctx)
        assert result == [99, 1, 2]

    def test_unknown_variable_raises(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        with pytest.raises(VariableResolutionError):
            resolver.resolve("${unknown_var}", ctx)

    def test_full_match_preserves_type(self) -> None:
        """${var} full match returns the typed value, not a string."""
        ctx = ExecutionContext(inputs={"count": 42})
        resolver = ReferenceResolver()
        result = resolver.resolve("${inputs.count}", ctx)
        assert result == 42
        assert isinstance(result, int)

    def test_resolve_saved_result(self) -> None:
        ctx = ExecutionContext()
        ctx.save_result("step_output", 3.14)
        resolver = ReferenceResolver()
        result = resolver.resolve("${step_output}", ctx)
        assert result == 3.14

    def test_resolve_empty_dict(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        result = resolver.resolve({}, ctx)
        assert result == {}

    def test_resolve_empty_list(self) -> None:
        ctx = ExecutionContext()
        resolver = ReferenceResolver()
        result = resolver.resolve([], ctx)
        assert result == []

    def test_nested_list_in_dict(self) -> None:
        ctx = ExecutionContext(inputs={"v": 7})
        resolver = ReferenceResolver()
        result = resolver.resolve({"items": ["${inputs.v}", 2]}, ctx)
        assert result == {"items": [7, 2]}
