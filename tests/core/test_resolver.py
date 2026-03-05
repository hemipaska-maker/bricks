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
