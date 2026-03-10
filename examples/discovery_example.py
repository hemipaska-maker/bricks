"""Example: automatic brick discovery from a directory.

This example demonstrates:
- Using BrickDiscovery to scan a directory for @brick-decorated functions
- Auto-registering discovered bricks in a BrickRegistry
- Listing all registered bricks with their schemas via registry_schema
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

from bricks.core.discovery import BrickDiscovery
from bricks.core.registry import BrickRegistry
from bricks.core.schema import registry_schema


def main() -> None:
    """Run the discovery example."""
    # Create a temporary directory with brick definitions
    with tempfile.TemporaryDirectory() as tmp_dir:
        bricks_dir = Path(tmp_dir)

        # Write two brick files into the temp directory
        (bricks_dir / "math_bricks.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Add two floats")
                def add(a: float, b: float) -> float:
                    return a + b

                @brick(tags=["math"], description="Multiply two floats")
                def multiply(a: float, b: float) -> float:
                    return a * b
            """).strip()
        )

        (bricks_dir / "string_bricks.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["string"], description="Convert to uppercase")
                def to_upper(text: str) -> str:
                    return text.upper()
            """).strip()
        )

        # Discover all bricks from the directory
        registry = BrickRegistry()
        discovery = BrickDiscovery(registry=registry)
        found = discovery.discover_package(bricks_dir)

        print(f"Discovered {len(found)} bricks: {sorted(found)}")

        # Print schemas for all discovered bricks
        schemas = registry_schema(registry)
        for schema in schemas:
            tags = ", ".join(schema["tags"]) if schema["tags"] else "none"
            print(f"  {schema['name']} [{tags}] -- {schema['description']}")
            for param, info in schema["parameters"].items():
                required = "required" if info["required"] else "optional"
                print(f"    param: {param} ({info['type']}, {required})")

        assert len(found) == 3, f"Expected 3 bricks, got {len(found)}"
        assert registry.has("add"), "Expected 'add' to be registered"
        assert registry.has("multiply"), "Expected 'multiply' to be registered"
        assert registry.has("to_upper"), "Expected 'to_upper' to be registered"

        # Verify bricks are callable
        add_fn, _ = registry.get("add")
        result = add_fn(a=3.0, b=4.0)
        assert result == 7.0, f"Expected add(3, 4) == 7.0, got {result}"

        to_upper_fn, _ = registry.get("to_upper")
        upper = to_upper_fn(text="hello")
        assert upper == "HELLO", f"Expected 'HELLO', got {upper}"

        print("\nAll assertions passed")


if __name__ == "__main__":
    main()
