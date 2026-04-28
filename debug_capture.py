"""Diagnostic shim for the for_each lambda extraction failure.

Patches:
  1. BlueprintComposer._parse_dsl_response — dumps raw LLM code before parsing
  2. bricks.core.dsl.for_each — on ValueError, logs the lambda shape + traceback

Run the reproducer through this shim:
    python debug_capture.py --case log-analysis --size 200 --model sonnet

Artifacts written to runs/notable/ so they're kept.
"""
from __future__ import annotations

import dis
import inspect
import io
import os
import sys
import time
import traceback
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows so Bricks log lines containing
# arrows or other non-cp1252 chars don't raise UnicodeEncodeError.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ART_DIR = Path(__file__).parent / "runs" / "notable"
ART_DIR.mkdir(parents=True, exist_ok=True)
STAMP = time.strftime("%Y%m%d-%H%M%S")

# ── Patch 1: dump raw composer code ──────────────────────────────────────────

from bricks.ai import composer as _comp

_orig_parse = _comp.BlueprintComposer._parse_dsl_response


def _patched_parse(self, raw_code: str):  # type: ignore[no-untyped-def]
    dump = ART_DIR / f"composer-raw-{STAMP}.py"
    dump.write_text(raw_code, encoding="utf-8")
    print(f"[debug_capture] raw composer code -> {dump} ({len(raw_code)} chars)")
    return _orig_parse(self, raw_code)


_comp.BlueprintComposer._parse_dsl_response = _patched_parse  # type: ignore[method-assign]

# ── Patch 2: log lambda shape on for_each ValueError ─────────────────────────

from bricks.core import dsl as _dsl

_orig_for_each = _dsl.for_each


def _patched_for_each(items, do, on_error: str = "fail"):  # type: ignore[no-untyped-def]
    try:
        return _orig_for_each(items, do, on_error=on_error)
    except ValueError as e:
        if "could not extract brick name" not in str(e):
            raise
        buf = io.StringIO()
        buf.write("=== LAMBDA SHAPE ===\n")
        try:
            buf.write(f"source:\n{inspect.getsource(do)}\n")
        except Exception as ge:  # noqa: BLE001
            buf.write(f"getsource failed: {ge}\n")
        code = getattr(do, "__code__", None)
        if code is not None:
            buf.write(f"co_name: {code.co_name}\n")
            buf.write(f"co_consts: {code.co_consts}\n")
            buf.write(f"co_names: {code.co_names}\n")
            buf.write(f"co_varnames: {code.co_varnames}\n")
            buf.write(f"co_freevars: {code.co_freevars}\n")
            buf.write(f"co_cellvars: {code.co_cellvars}\n")
            buf.write("dis:\n")
            # capture dis output
            old_stdout = sys.stdout
            sys.stdout = dbuf = io.StringIO()
            try:
                dis.dis(do)
            finally:
                sys.stdout = old_stdout
            buf.write(dbuf.getvalue())
        buf.write("--- traceback ---\n")
        buf.write(traceback.format_exc())
        buf.write("=== END ===\n")
        out = buf.getvalue()
        dump = ART_DIR / f"for_each-lambda-{STAMP}.txt"
        dump.write_text(out, encoding="utf-8")
        # Also print to stdout so it shows in task output
        print(out)
        print(f"[debug_capture] lambda shape → {dump}")
        raise


# Re-export so the composer's `from bricks.core.dsl import ... for_each` captures patched symbol.
# Composer imported for_each at module load time, so we need to overwrite the symbol it already bound.
_dsl.for_each = _patched_for_each
_comp.for_each = _patched_for_each  # composer has `from bricks.core.dsl import for_each`

# Composer also puts for_each into the exec namespace — that dict is built at call time
# from `_comp.for_each`, so the rebind above is sufficient.

if __name__ == "__main__":
    # Hand control to the runner with sys.argv intact.
    import runpy

    runner = Path(__file__).parent / "tracks" / "track-1-exploration" / "run.py"
    sys.argv = [str(runner)] + sys.argv[1:]
    runpy.run_path(str(runner), run_name="__main__")
