"""AI generation for live mode: calls Anthropic API to generate YAML and Python."""

from __future__ import annotations

import os
from typing import Any

from bricks.core import BrickRegistry


def generate_bricks_yaml(
    intent: str,
    registry: BrickRegistry,
) -> tuple[str, int]:
    """Generate Bricks YAML via SequenceComposer.

    Returns:
        (yaml_string, input_tokens_used)

    Note: Token count is estimated from the request since SequenceComposer
    does not expose token usage from the underlying Anthropic API call.
    """
    try:
        from bricks.ai import SequenceComposer
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install -e '.[ai]'"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it or use demo mode (no --live flag)."
        )

    composer = SequenceComposer(registry=registry, api_key=api_key)
    sequence = composer.compose(intent)
    yaml_str = _sequence_to_yaml(sequence)

    # Estimate tokens from YAML output and brick schemas
    # Rough estimate: ~4 characters = 1 token
    yaml_tokens = len(yaml_str) // 4
    # Add ~960 tokens for Bricks system prompt in SequenceComposer
    # and ~200 tokens per brick in registry for context
    system_and_context_tokens = 960 + (len(registry.get_all_brick_names()) * 200)
    estimated_total = system_and_context_tokens + yaml_tokens

    return yaml_str, estimated_total


def generate_python_code(
    intent: str,
    available_functions: list[tuple[str, str]],
) -> tuple[str, int]:
    """Generate Python code via Anthropic API.

    Args:
        intent: Natural language description of what to compute
        available_functions: List of (function_name, docstring) tuples

    Returns:
        (python_code, total_tokens_used)

    Token count includes both input and output tokens from the API response.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install -e '.[ai]'"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it or use demo mode (no --live flag)."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Build function descriptions
    func_descriptions = "\n".join(
        f"- {name}: {doc}" for name, doc in available_functions
    )

    system_prompt = (
        "You are an expert Python programmer. "
        "Generate Python code that solves the given task.\n\n"
        "Available functions:\n"
        f"{func_descriptions}\n\n"
        "Requirements:\n"
        "- Use only the available functions listed above\n"
        "- Do NOT import any modules or define new functions\n"
        "- Store the final result in a variable named 'result' as a dict\n"
        "- The code must be runnable with exec()\n"
        "- Assume 'inputs' is a dict of input parameters already defined\n\n"
        "Output ONLY the Python code, no explanations."
    )

    user_prompt = f"""Task: {intent}

Generate Python code that solves this task using the available functions."""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    code = response.content[0].text
    # Return total tokens: input + output
    total_tokens = response.usage.input_tokens + response.usage.output_tokens
    return code, total_tokens


def _sequence_to_yaml(sequence: Any) -> str:
    """Convert a SequenceDefinition to YAML string."""
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False

    data = {
        "name": sequence.name,
        "description": sequence.description,
        "inputs": sequence.inputs,
        "steps": [
            {
                "name": step.name,
                "brick": step.brick,
                "params": step.params,
                **({"save_as": step.save_as} if step.save_as else {}),
            }
            for step in sequence.steps
        ],
        "outputs_map": sequence.outputs_map,
    }

    import io

    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()
