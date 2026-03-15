"""Data bricks: http_get (mock) and json_extract."""

from __future__ import annotations

import copy
from typing import Any

from bricks.core import brick

# Mock response returned by http_get regardless of URL (no real HTTP calls)
_MOCK_RESPONSE = {
    "status_code": 200,
    "body": {
        "users": [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Carol", "age": 35},
        ]
    },
}


@brick(tags=["network"], destructive=False)
def http_get(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Fetch data from a URL (mock: returns hardcoded user data for benchmarking)."""
    return copy.deepcopy(_MOCK_RESPONSE)


@brick(tags=["data"], destructive=False)
def json_extract(data: Any, path: str) -> dict[str, Any]:
    """Extract a value from a dict/list using a dot-separated path.

    Example: path="users.0.name" on {"users": [{"name": "Alice"}]} returns "Alice".
    """
    current: Any = data
    for part in path.split("."):
        try:
            current = current[int(part)] if isinstance(current, list) else current[part]
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"Invalid path segment {part!r} in path {path!r}: {exc}") from exc
    return {"value": current}
