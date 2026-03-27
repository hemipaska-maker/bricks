# Scenario D: Determinism Benchmark

> **Claim:** Code generation produces a different program every time.  
> Bricks Blueprints produce identical execution every time.

## Diff: Generation 1 vs Generation 3

Same prompt. Same model. Different output.

```diff
--- generation_1.py
+++ generation_3.py
@@ -2,43 +2,53 @@
     """
     Calculate the area of a room given its width and height.
     
+    Multiplies width by height, rounds the result to 2 decimal places,
+    and returns both the numeric area and a formatted display string.
+    
     Args:
-        width: The width of the room in meters. Must be positive.
-        height: The height of the room in meters. Must be positive.
+        width: The width of the room in units. Must be positive.
+        height: The height of the room in units. Must be positive.
     
     Returns:
         A dictionary containing:
-            - 'area': The calculated area rounded to 2 decimal places
-            - 'display': A formatted display string with the result
+        - 'area': The calculated area rounded to 2 decimal places
+        - 'display': A formatted string representation of the result
     
     Raises:
-        ValueError: If width or height is not positive.
-        TypeError: If width or height is not a valid number.
+        ValueError: If width or height is not positive (> 0)
+        TypeError: If width or height is not a valid number
+    
+    Example:
+        >>> result = calculate_room_area(5.5, 4.2)
+        >>> result['area']
+        23.1
+        >>> 'Room Area' in result['display']
+        True
     """
-    # Input validation
-    if not isinstance(width, (int, float)) or isinstance(width, bool):
-        raise TypeError(f"width must be a number, got {type(width).__name__}")
-    if not isinstance(height, (int, float)) or isinstance(height, bool):
-        raise TypeError(f"height must be a number, got {type(height).__name__}")
+    try:
+        width = float(width)
+        height = float(height)
+    except (TypeError, ValueError):
+        raise TypeError("Width and height must be valid numbers")
     
     if width <= 0:
-        raise ValueError(f"width must be positive, got {width}")
+        raise ValueError("Width must be a positive number (> 0)")
     if height <= 0:
-        raise ValueError(f"height must be positive, got {height}")
+        raise ValueError("Height must be a positive number (> 0)")
     
-    # Calculate area by multiplying width and height
+    # Multiply width and height
     multiplication_result = multiply(width, height)
-    area_value = multiplication_result['result']
+    raw_area = multiplication_result['result']
     
     # Round to 2 decimal places
-    rounded_result = round_value(area_value, decimals=2)
-    rounded_area = rounded_result['result']
+    rounded_result = round_value(raw_area, decimals=2)
+    area = rounded_result['result']
     
     # Format the result for display
-    formatted_result = format_result("Room Area", rounded_area)
-    display_string = formatted_result['display']
+    format_result_dict = format_result("Room Area", area)
+    display = format_result_dict['display']
     
     return {
-        'area': rounded_area,
-        'display': display_string
+        'area': area,
+        'display': display
     }
```

## Metrics

| Metric | Code Generation (5 runs) | Bricks Blueprint (5 runs) |
|--------|--------------------------|---------------------------|
| Unique variable names | 19 distinct names across runs | N/A — no variables, just YAML wiring |
| Unique function signatures | 1 distinct signature(s) | N/A — Blueprint schema is fixed |
| Error handling consistent | ✓, ✓, ✓, ✓, ✓ | Always — Brick has it built-in |
| Docstring length (chars) | 538, 536, 850, 703, 539 | N/A — Brick has fixed description |
| Lines of code | 36, 36, 44, 37, 33 | Blueprint is always the same 27 lines |
| Exact duplicate outputs | 0 pair(s) identical | All 5 executions identical (same YAML) |
| Pre-execution validation | None — code runs and you hope | ✓, ✓, ✓, ✓, ✓ — dry-run before every run |

## The Blueprint

This is the same file used in all 5 executions. It will never change.

```yaml
name: room_area
description: "Calculate room area, round it, and format a display string"
inputs:
  width: "float"
  height: "float"
steps:
  - name: calculate_area
    brick: multiply
    params:
      a: "${inputs.width}"
      b: "${inputs.height}"
    save_as: area
  - name: round_area
    brick: round_value
    params:
      value: "${area.result}"
      decimals: 2
    save_as: rounded
  - name: format_display
    brick: format_result
    params:
      label: "Area (m2)"
      value: "${rounded.result}"
    save_as: formatted
outputs_map:
  area: "${rounded.result}"
  display: "${formatted.display}"
```

## Conclusion

Code generation produces a different program every time. Across 5 runs with the identical prompt, the model used 19 distinct variable names, sometimes varied its error handling, and produced functions ranging from 33 to 44 lines. Some are better, some are worse — you cannot predict which. Bricks produces the same execution every time: the Blueprint is validated once, stored as a YAML file, and executed identically on every subsequent run. You validate once, trust forever.

## Hallucination Detection

In this run, **1/5** generation(s) had at least one issue.

- **Generation 1:** hallucinated_function:type, hallucinated_function:type
- **Generation 2:** clean
- **Generation 3:** clean
- **Generation 4:** clean
- **Generation 5:** clean

_Note: This rate varies — repeated benchmarks may show different results, which itself proves the non-determinism._
