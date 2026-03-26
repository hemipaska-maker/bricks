"""Standard library of pre-built bricks — 95 bricks across 7 categories.

Usage::

    from bricks.stdlib import build_stdlib_registry
    registry = build_stdlib_registry()
"""

from __future__ import annotations

from bricks.core.registry import BrickRegistry
from bricks.stdlib import (
    data_transformation,
    date_time,
    encoding_security,
    list_operations,
    math_numeric,
    string_processing,
    validation,
)

__all__ = ["build_stdlib_registry"]


def build_stdlib_registry() -> BrickRegistry:
    """Create and return a BrickRegistry pre-loaded with all 95 stdlib bricks.

    Returns:
        BrickRegistry containing all stdlib bricks across 7 categories:
        data_transformation (25), string_processing (20), math_numeric (10),
        date_time (10), validation (10), list_operations (10),
        encoding_security (10).
    """
    registry = BrickRegistry()

    modules = [
        data_transformation,
        string_processing,
        math_numeric,
        date_time,
        validation,
        list_operations,
        encoding_security,
    ]

    for module in modules:
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, "__brick_meta__"):
                registry.register(name, obj, obj.__brick_meta__)

    return registry
