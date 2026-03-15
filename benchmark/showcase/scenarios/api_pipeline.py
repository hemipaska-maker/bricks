"""Scenario B: API pipeline — fetch, extract, format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.showcase.tokens import count_tokens

_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

_CODEGEN_SYSTEM = (
    "You are an expert Python programmer. Generate production-ready Python "
    "code using ONLY the provided helper functions. Do not import anything."
)

_CODEGEN_USER = """\
Available helper functions (use ONLY these):

def http_get(url: str, headers: dict = {}) -> dict:
    \"\"\"Fetch data from a URL. Returns {'status_code': int, 'body': dict}.\"\"\"

def json_extract(data: any, path: str) -> dict:
    \"\"\"Extract value using dot-separated path (e.g. 'users.0.name').
    Returns {'value': any}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {'display': str}.\"\"\"

Task: Write `fetch_user_field(api_url: str, user_index: int, field: str) -> dict`
that calls http_get(), json_extract() to get users list then the specific field,
and format_result() to format the output.
Return {'value': any, 'display': str}. Include type hints, docstring, error handling.
"""

_GENERATED_CODE = '''\
import requests
from typing import Any


def fetch_and_extract_user(
    url: str,
    user_index: int,
    field: str,
    timeout: int = 10,
) -> dict[str, Any]:
    """Fetch user data from an API and extract a specific field.

    Args:
        url: API endpoint URL.
        user_index: Index into the users list.
        field: Field name to extract from the user dict.
        timeout: Request timeout in seconds.

    Returns:
        dict with \'value\' (extracted value) and \'display\' (formatted string).

    Raises:
        requests.HTTPError: If the HTTP request fails.
        KeyError: If the expected fields are missing from the response.
        IndexError: If user_index is out of range.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request to {url} timed out after {timeout}s")
    except requests.exceptions.ConnectionError as exc:
        raise ConnectionError(f"Could not connect to {url}: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(f"Response from {url} is not valid JSON") from exc

    try:
        users = data["users"]
        user = users[user_index]
        value = user[field]
    except (KeyError, IndexError) as exc:
        raise KeyError(
            f"Could not extract users[{user_index}].{field} from response"
        ) from exc

    display = f"Extracted value: {value}"
    return {"value": value, "display": display}
'''

_BRICK_SCHEMAS = [
    {
        "name": "http_get",
        "description": "Fetch data from a URL (mock for benchmarking).",
        "parameters": {"url": "str", "headers": "dict"},
        "returns": {"status_code": "int", "body": "dict"},
    },
    {
        "name": "json_extract",
        "description": "Extract a value using a dot-separated path.",
        "parameters": {"data": "any", "path": "str"},
        "returns": {"value": "any"},
    },
    {
        "name": "format_result",
        "description": "Format a labelled numeric result as a display string.",
        "parameters": {"label": "str", "value": "float"},
        "returns": {"display": "str"},
    },
]

_INTENT = (
    "Fetch user data from an API URL, extract a specific field from a user "
    "at a given index, and format the result as a display string."
)


def code_generation_approach() -> dict[str, Any]:
    """Return token cost and simulated code for the raw code-gen approach."""
    prompt = _CODEGEN_SYSTEM + "\n\n" + _CODEGEN_USER
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(_GENERATED_CODE)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "code": _GENERATED_CODE,
    }


def bricks_approach() -> dict[str, Any]:
    """Return token cost and execute the Blueprint for the Bricks approach."""
    schema_payload = json.dumps(_BRICK_SCHEMAS, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "api_pipeline.yaml").read_text()
    prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {_INTENT}"
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(blueprint_yaml)

    result = _execute_blueprint(
        blueprint_yaml,
        {"api_url": "https://api.example.com/users", "user_index": 0, "field": "name"},
    )

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "blueprint": blueprint_yaml,
        "execution_result": result,
    }


def _execute_blueprint(yaml_str: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Load and run the blueprint through the Bricks engine."""
    from benchmark.showcase.bricks.data_bricks import http_get, json_extract
    from benchmark.showcase.bricks.string_bricks import format_result
    from bricks.core import BrickRegistry, SequenceEngine, SequenceLoader

    registry = BrickRegistry()
    for fn in (http_get, json_extract, format_result):
        registry.register(fn.__name__, fn, fn.__brick_meta__)  # type: ignore[attr-defined]

    loader = SequenceLoader()
    engine = SequenceEngine(registry=registry)
    sequence = loader.load_string(yaml_str)
    return engine.run(sequence, inputs=inputs)
