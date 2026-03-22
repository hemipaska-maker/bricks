"""Tool executor: simulates MCP tool calls using the real Bricks engine.

Extracted from agent_runner.py to separate orchestration from execution.
"""

from __future__ import annotations

import re
from typing import Any

from bricks.core.catalog import TieredCatalog
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import (
    BlueprintValidationError,
    BrickExecutionError,
    BrickNotFoundError,
    VariableResolutionError,
    YamlLoadError,
)
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import BlueprintValidator


def execute_tool(
    name: str,
    inputs: dict[str, Any],
    catalog: TieredCatalog,
    engine: BlueprintEngine,
    loader: BlueprintLoader,
    validator: BlueprintValidator,
) -> Any:
    """Execute a simulated MCP tool call using the real Bricks engine.

    Args:
        name: Tool name (``list_bricks``, ``lookup_brick``, ``execute_blueprint``).
        inputs: Tool input parameters dict.
        catalog: TieredCatalog for brick discovery.
        engine: BlueprintEngine for execution.
        loader: BlueprintLoader for parsing YAML strings.
        validator: BlueprintValidator for pre-execution validation.

    Returns:
        JSON-serialisable tool result.
    """
    if name == "list_bricks":
        return catalog.list_bricks()
    if name == "lookup_brick":
        return catalog.lookup_brick(inputs["query"])
    if name == "execute_blueprint":
        return _execute_blueprint(inputs, catalog, engine, loader, validator)
    return {"error": f"Unknown tool: {name}"}


def _execute_blueprint(
    inputs: dict[str, Any],
    catalog: TieredCatalog,
    engine: BlueprintEngine,
    loader: BlueprintLoader,
    validator: BlueprintValidator,
) -> dict[str, Any]:
    """Execute an execute_blueprint tool call.

    Args:
        inputs: Tool input dict with ``blueprint_yaml`` and optional ``inputs``.
        catalog: TieredCatalog for brick discovery.
        engine: BlueprintEngine for execution.
        loader: BlueprintLoader for parsing.
        validator: BlueprintValidator for pre-execution validation.

    Returns:
        Result dict with ``success``, ``outputs``, and optional ``error``/``hint``.
    """
    bp_yaml: str = inputs["blueprint_yaml"]
    bp_inputs: dict[str, Any] = inputs.get("inputs") or {}
    try:
        bp = loader.load_string(bp_yaml)
        validator.validate(bp)
        result = engine.run(bp, inputs=bp_inputs).outputs
        return {"success": True, "outputs": result}
    except BrickNotFoundError as exc:
        available = [n for n, _ in catalog._registry.list_all()]
        match = fuzzy_match(exc.name, available)
        hint = f"Did you mean '{match}'? " if match else ""
        hint += f"Available bricks: {', '.join(sorted(available))}"
        return {"success": False, "error": str(exc), "hint": hint}
    except BlueprintValidationError as exc:
        available = [n for n, _ in catalog._registry.list_all()]
        save_as_names = extract_save_as_names(bp_yaml)
        hint = validation_hint(exc.errors, available, save_as_names)
        return {
            "success": False,
            "error": str(exc),
            "all_errors": exc.errors,
            "hint": hint,
        }
    except VariableResolutionError as exc:
        save_as_names = extract_save_as_names(bp_yaml)
        hint = f"Reference '{exc.reference}' failed. Available save_as names: {save_as_names}"
        return {"success": False, "error": str(exc), "hint": hint}
    except BrickExecutionError as exc:
        hint = f"Brick '{exc.brick_name}' failed at step '{exc.step_name}': {exc.cause}"
        param_hint = brick_param_hint(catalog._registry, exc.brick_name)
        if param_hint:
            hint += f". Expected params: {param_hint}"
        return {"success": False, "error": str(exc), "hint": hint}
    except YamlLoadError as exc:
        return {
            "success": False,
            "error": str(exc),
            "hint": "YAML parse error. Check indentation and syntax.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def validation_hint(
    errors: list[str],
    available_bricks: list[str],
    save_as_names: list[str],
) -> str:
    """Build an actionable hint from validation errors.

    Args:
        errors: List of validation error strings.
        available_bricks: List of valid brick names.
        save_as_names: List of save_as names found in the blueprint.

    Returns:
        Actionable hint string.
    """
    hints: list[str] = []
    for err in errors:
        brick_match = re.search(r"brick '(\w+)' not found", err)
        if brick_match:
            bad_name = brick_match.group(1)
            suggestion = fuzzy_match(bad_name, available_bricks)
            hint = f"Did you mean '{suggestion}'? " if suggestion else ""
            hint += f"Available bricks: {', '.join(sorted(available_bricks))}"
            hints.append(hint)
            continue
        var_match = re.search(r"undefined variable '(\S+)'", err)
        if var_match:
            hints.append(f"Available save_as names: {save_as_names}")
            continue
    if not hints:
        return "Fix all errors listed in all_errors and retry."
    return " | ".join(hints)


def fuzzy_match(name: str, available: list[str]) -> str | None:
    """Find the closest match for a brick name using substring/prefix matching.

    Args:
        name: The unrecognized brick name.
        available: List of valid brick names.

    Returns:
        The closest match, or None if no reasonable match found.
    """
    name_lower = name.lower()
    for candidate in available:
        if candidate.lower().startswith(name_lower) or name_lower.startswith(candidate.lower()):
            return candidate
    for candidate in available:
        if name_lower in candidate.lower() or candidate.lower() in name_lower:
            return candidate
    return None


def extract_save_as_names(bp_yaml: str) -> list[str]:
    """Extract save_as names from a blueprint YAML string.

    Args:
        bp_yaml: Raw YAML string of the blueprint.

    Returns:
        List of save_as values found in the YAML.
    """
    return re.findall(r"save_as:\s*(\S+)", bp_yaml)


def brick_param_hint(registry: BrickRegistry, brick_name: str) -> str:
    """Format expected parameter info for a brick.

    Args:
        registry: The brick registry.
        brick_name: Name of the brick.

    Returns:
        Formatted parameter string, or empty string if brick not found.
    """
    try:
        from bricks.core.schema import signature_params

        callable_, _ = registry.get(brick_name)
        return signature_params(callable_)
    except Exception:  # noqa: S110
        pass
    return ""
