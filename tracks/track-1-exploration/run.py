"""Track 1 — Exploration runner.

One invocation = one (case, size, model) combination. Runs Bricks end-to-end
and a raw-LLM baseline, compares both against the case's ground truth, and
emits the charter's data contract: one immutable JSON in ``runs/`` plus one
appended line in ``manifest/track-1.jsonl``.

Usage:

    python tracks/track-1-exploration/run.py \\
        --case log-analysis --size 200 --model sonnet

Cases live in ``cases/<slug>/`` with ``data-<size>.json`` +
``data-<size>.truth.json`` pairs (see ``cases/log-analysis/generate.py``).

The raw-LLM baseline is a single prompt that gives the model the full input
and asks for the JSON output directly — no tooling, no chain-of-thought
scaffolding. That's the point: it's the "just ask the LLM" comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import uuid

# Force UTF-8 stdout/stderr on Windows — Bricks engine logs arrows (→) and
# other non-cp1252 chars that crash the default Windows console encoding.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bricks import Bricks
from bricks.llm.base import CompletionResult, LLMProvider
from bricks.providers.claudecode.provider import ClaudeCodeProvider

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "runs"
MANIFEST_PATH = REPO_ROOT / "manifest" / "track-1.jsonl"
CASES_DIR = REPO_ROOT / "cases"

TRACK = "track-1-exploration"
RUNNER_REL = "tracks/track-1-exploration/run.py"


# ─── Provider wrapper that accumulates cost + tokens across calls ────────────


class AccumulatingProvider(LLMProvider):
    """Delegates to an inner provider and sums cost/tokens over every call.

    Bricks' engine makes N LLM calls per ``execute()`` (compose + heal + etc.);
    the per-call numbers live on each ``CompletionResult``. This wrapper gives
    us a single aggregate view without reaching into orchestrator internals.
    """

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.calls: list[CompletionResult] = []

    def complete(self, prompt: str, system: str = "") -> CompletionResult:
        res = self._inner.complete(prompt, system)
        self.calls.append(res)
        return res

    def totals(self) -> dict[str, Any]:
        return {
            "input": sum(c.input_tokens for c in self.calls),
            "output": sum(c.output_tokens for c in self.calls),
            "cache_read": sum(c.cached_input_tokens for c in self.calls),
            "cache_creation": sum(c.cache_creation_input_tokens for c in self.calls),
            "cost_usd": sum(c.cost_usd for c in self.calls),
            "n_calls": len(self.calls),
            "any_estimated": any(c.estimated for c in self.calls),
        }


# ─── Per-case task specifications ────────────────────────────────────────────
#
# Each case declares the prompts Bricks and the raw-LLM baseline see, plus a
# verifier. Kept in one dict so adding a case = adding a key, no framework
# changes.


def _numeric_verify(keys: tuple[str, ...]) -> Any:
    """Build a verifier that checks the given subset of numeric-stat keys."""
    def _verify(output: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
        diffs: list[dict[str, Any]] = []
        for key in keys:
            got = output.get(key)
            exp = truth[key]
            if key == "count":
                if got != exp:
                    diffs.append({"field": key, "expected": exp, "got": got})
            else:
                if got is None or not isinstance(got, (int, float)) or abs(float(got) - exp) > 1e-6:
                    diffs.append({"field": key, "expected": exp, "got": got})
        return {"correct": not diffs, "per_field_diffs": diffs}
    return _verify


_numeric_stats_verify = _numeric_verify(("sum", "mean", "min", "max", "count"))
_sum_only_verify = _numeric_verify(("sum",))
_count_only_verify = _numeric_verify(("count",))
_max_only_verify = _numeric_verify(("max",))
_mean_only_verify = _numeric_verify(("mean",))


def _no_auto_verify(output: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Counter-case verifier — records outputs but never auto-judges.

    For tasks where 'correct' is subjective (style, judgment, generation), we
    can't claim correctness without a human eval. Record both engines' outputs
    in the run JSON and inspect manually.
    """
    return {"correct": False, "per_field_diffs": [{"note": "subjective task — manual review required"}]}


# ─── Reliability-sweep verifiers (compute truth from data on the fly) ────────


def _close(a: float, b: float, tol: float = 1e-3) -> bool:
    return isinstance(a, (int, float)) and abs(float(a) - float(b)) < tol


def _verify_min(out, truth, *, data):
    expected = min(data)
    got = out.get("min")
    diffs = [] if _close(got, expected) else [{"field": "min", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_count_gt50(out, truth, *, data):
    expected = sum(1 for v in data if v > 50)
    got = out.get("count")
    diffs = [] if got == expected else [{"field": "count", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_sum_gt50(out, truth, *, data):
    expected = sum(v for v in data if v > 50)
    got = out.get("sum")
    diffs = [] if _close(got, expected, tol=1e-2) else [{"field": "sum", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_count_lt10(out, truth, *, data):
    expected = sum(1 for v in data if v < 10)
    got = out.get("count")
    diffs = [] if got == expected else [{"field": "count", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_top3_desc(out, truth, *, data):
    expected = sorted(data, reverse=True)[:3]
    got = out.get("top")
    if not isinstance(got, list) or len(got) != 3:
        return {"correct": False, "per_field_diffs": [{"field": "top", "expected": expected, "got": got}]}
    correct = all(_close(g, e) for g, e in zip(got, expected))
    return {"correct": correct, "per_field_diffs": [] if correct else [{"field": "top", "expected": expected, "got": got}]}


def _verify_bottom3_asc(out, truth, *, data):
    expected = sorted(data)[:3]
    got = out.get("bottom")
    if not isinstance(got, list) or len(got) != 3:
        return {"correct": False, "per_field_diffs": [{"field": "bottom", "expected": expected, "got": got}]}
    correct = all(_close(g, e) for g, e in zip(got, expected))
    return {"correct": correct, "per_field_diffs": [] if correct else [{"field": "bottom", "expected": expected, "got": got}]}


def _verify_squared_sum(out, truth, *, data):
    expected = sum(v * v for v in data)
    got = out.get("sum")
    diffs = [] if _close(got, expected, tol=1.0) else [{"field": "sum", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_median(out, truth, *, data):
    import statistics as _st
    expected = _st.median(data)
    got = out.get("median")
    diffs = [] if _close(got, expected, tol=1e-2) else [{"field": "median", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_range(out, truth, *, data):
    diffs = []
    for k, e in (("min", min(data)), ("max", max(data)), ("range", max(data) - min(data))):
        if not _close(out.get(k), e):
            diffs.append({"field": k, "expected": e, "got": out.get(k)})
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_string_lengths(out, truth, *, data):
    expected = [len(s) for s in data]
    got = out.get("lengths")
    diffs = [] if got == expected else [{"field": "lengths", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_string_uppercase(out, truth, *, data):
    expected = [s.upper() for s in data]
    got = out.get("upper")
    diffs = [] if got == expected else [{"field": "upper", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_string_join(out, truth, *, data):
    expected = ",".join(data)
    got = out.get("joined")
    diffs = [] if got == expected else [{"field": "joined", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_extract_names(out, truth, *, data):
    expected = [r["name"] for r in data]
    got = out.get("names")
    diffs = [] if got == expected else [{"field": "names", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_dedup_count(out, truth, *, data):
    expected = len(set(data))
    got = out.get("unique_count")
    diffs = [] if got == expected else [{"field": "unique_count", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _verify_sort_asc_full(out, truth, *, data):
    expected = sorted(set(data))
    got = out.get("unique_sorted")
    diffs = [] if got == expected else [{"field": "unique_sorted", "expected": expected, "got": got}]
    return {"correct": not diffs, "per_field_diffs": diffs}


def _log_analysis_verify(output: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []
    if output.get("severity_counts") != truth["severity_counts"]:
        diffs.append({"field": "severity_counts", "expected": truth["severity_counts"], "got": output.get("severity_counts")})
    if output.get("top_error_patterns") != truth["top_error_patterns"]:
        diffs.append({"field": "top_error_patterns", "expected": truth["top_error_patterns"], "got": output.get("top_error_patterns")})
    return {"correct": not diffs, "per_field_diffs": diffs}


CASES: dict[str, dict[str, Any]] = {
    "log-analysis": {
        "bricks_task": (
            "Given a list of log line strings under inputs.log_lines, compute "
            "(a) severity_counts: a dict mapping each severity in "
            "[INFO, WARN, ERROR, DEBUG] to the count of parseable lines at that "
            "severity (unparseable lines are ignored), and (b) top_error_patterns: "
            "the top 3 distinct message strings among ERROR lines, as a list of "
            "{pattern, count} dicts sorted by count descending then pattern "
            "ascending. Log line format is "
            "'<ISO-timestamp> <SEVERITY> <service> - <message>' with some noise."
        ),
        "bricks_input_key": "log_lines",
        "raw_llm_prompt": (
            "You are given a JSON array of log line strings. Each line follows "
            "'<ISO-timestamp> <SEVERITY> <service> - <message>' with some "
            "noise (extra whitespace, lowercase severity, or malformed lines "
            "with no severity — skip those silently).\n\n"
            "Return ONLY a JSON object with exactly these keys:\n"
            "  severity_counts: dict mapping INFO/WARN/ERROR/DEBUG to integer "
            "counts of parseable lines at that severity.\n"
            "  top_error_patterns: list of the top 3 distinct message strings "
            "among ERROR lines, as [{{\"pattern\": str, \"count\": int}}], "
            "sorted by count desc then pattern asc.\n\n"
            "Output only the JSON, no prose, no code fences.\n\n"
            "LOG LINES:\n{data_json}"
        ),
        "verify": _log_analysis_verify,
    },
    "sum-only": {
        "bricks_task": (
            "Given a list of numbers under inputs.values, return {\"sum\": S} "
            "where S is the arithmetic sum of all the values."
        ),
        "bricks_input_key": "values",
        "raw_llm_prompt": (
            "Given a JSON array of numbers, return ONLY a JSON object "
            '{{"sum": S}} where S is the arithmetic sum.\n\nVALUES:\n{data_json}'
        ),
        "verify": _sum_only_verify,
        "data_case": "numeric-stats",
    },
    "count-only": {
        "bricks_task": (
            "Given a list of numbers under inputs.values, return {\"count\": N} "
            "where N is the number of values in the list."
        ),
        "bricks_input_key": "values",
        "raw_llm_prompt": (
            "Given a JSON array of numbers, return ONLY a JSON object "
            '{{"count": N}} where N is the length.\n\nVALUES:\n{data_json}'
        ),
        "verify": _count_only_verify,
        "data_case": "numeric-stats",
    },
    "max-only": {
        "bricks_task": (
            "Given a list of numbers under inputs.values, return {\"max\": M} "
            "where M is the largest value in the list."
        ),
        "bricks_input_key": "values",
        "raw_llm_prompt": (
            "Given a JSON array of numbers, return ONLY a JSON object "
            '{{"max": M}} where M is the largest.\n\nVALUES:\n{data_json}'
        ),
        "verify": _max_only_verify,
        "data_case": "numeric-stats",
    },
    "mean-only": {
        "bricks_task": (
            "Given a list of numbers under inputs.values, return {\"mean\": M} "
            "where M is the arithmetic mean (average) of the values."
        ),
        "bricks_input_key": "values",
        "raw_llm_prompt": (
            "Given a JSON array of numbers, return ONLY a JSON object "
            '{{"mean": M}} where M is the arithmetic mean.\n\nVALUES:\n{data_json}'
        ),
        "verify": _mean_only_verify,
        "data_case": "numeric-stats",
    },
    "email-rewrite": {
        "bricks_task": (
            "Given the customer email under inputs.email_text, rewrite it in a "
            "warmer, more polite tone while preserving the original meaning and "
            "any factual details. Return {\"rewritten\": <new_text>}."
        ),
        "bricks_input_key": "email_text",
        "raw_llm_prompt": (
            "Rewrite the following customer email in a warmer, more polite tone, "
            "preserving the meaning and all factual details.\n\n"
            'Return ONLY a JSON object: {{"rewritten": <new_text>}}. No prose, no fences.\n\n'
            "EMAIL:\n{data_json}"
        ),
        "verify": _no_auto_verify,
        "data_case": "email-rewrite",
    },
    # ── Reliability sweep (15 task shapes) ──────────────────────────────────
    "min-only": {
        "bricks_task": "Given a list of numbers under inputs.values, return {\"min\": M} where M is the smallest value.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, return ONLY {{"min": M}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_min,
        "data_case": "numeric-stats",
    },
    "count-gt50": {
        "bricks_task": "Given a list of numbers under inputs.values, count how many are strictly greater than 50, return {\"count\": N}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, count how many are > 50. Return ONLY {{"count": N}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_count_gt50,
        "data_case": "numeric-stats",
    },
    "sum-gt50": {
        "bricks_task": "Given a list of numbers under inputs.values, sum the values that are strictly greater than 50, return {\"sum\": S}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, sum the ones > 50. Return ONLY {{"sum": S}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_sum_gt50,
        "data_case": "numeric-stats",
    },
    "count-lt10": {
        "bricks_task": "Given a list of numbers under inputs.values, count how many are strictly less than 10, return {\"count\": N}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, count how many are < 10. Return ONLY {{"count": N}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_count_lt10,
        "data_case": "numeric-stats",
    },
    "top3-desc": {
        "bricks_task": "Given a list of numbers under inputs.values, return the 3 largest values in descending order as {\"top\": [a, b, c]}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, return the top 3 in descending order. ONLY {{"top": [a, b, c]}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_top3_desc,
        "data_case": "numeric-stats",
    },
    "bottom3-asc": {
        "bricks_task": "Given a list of numbers under inputs.values, return the 3 smallest values in ascending order as {\"bottom\": [a, b, c]}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, return the bottom 3 in ascending order. ONLY {{"bottom": [a, b, c]}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_bottom3_asc,
        "data_case": "numeric-stats",
    },
    "squared-sum": {
        "bricks_task": "Given a list of numbers under inputs.values, square each value and return {\"sum\": S} of the squares.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, sum each value squared. ONLY {{"sum": S}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_squared_sum,
        "data_case": "numeric-stats",
    },
    "median-only": {
        "bricks_task": "Given a list of numbers under inputs.values, return the median as {\"median\": M}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, return the median. ONLY {{"median": M}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_median,
        "data_case": "numeric-stats",
    },
    "range-stats": {
        "bricks_task": "Given a list of numbers under inputs.values, return {\"min\": m, \"max\": M, \"range\": M-m}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of numbers, return ONLY {{"min": m, "max": M, "range": M-m}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_range,
        "data_case": "numeric-stats",
    },
    "string-lengths": {
        "bricks_task": "Given a list of strings under inputs.strings, return {\"lengths\": [...]} the character-length of each string.",
        "bricks_input_key": "strings",
        "raw_llm_prompt": 'Given a JSON array of strings, return ONLY {{"lengths": [...]}} listing the char length of each.\n\nSTRINGS:\n{data_json}',
        "verify": _verify_string_lengths,
        "data_case": "string-fruits",
    },
    "string-uppercase": {
        "bricks_task": "Given a list of strings under inputs.strings, return {\"upper\": [...]} with each string uppercased.",
        "bricks_input_key": "strings",
        "raw_llm_prompt": 'Given a JSON array of strings, return ONLY {{"upper": [...]}} with each string uppercased.\n\nSTRINGS:\n{data_json}',
        "verify": _verify_string_uppercase,
        "data_case": "string-fruits",
    },
    "string-join": {
        "bricks_task": "Given a list of strings under inputs.strings, return {\"joined\": s} with all strings joined by a comma (no space).",
        "bricks_input_key": "strings",
        "raw_llm_prompt": 'Given a JSON array of strings, return ONLY {{"joined": s}} with all joined by a comma (no space).\n\nSTRINGS:\n{data_json}',
        "verify": _verify_string_join,
        "data_case": "string-fruits",
    },
    "extract-names": {
        "bricks_task": "Given a list of records under inputs.records (each {name, age}), return {\"names\": [...]} the name of each record in order.",
        "bricks_input_key": "records",
        "raw_llm_prompt": 'Given a JSON array of {{name, age}} records, return ONLY {{"names": [...]}} the names in order.\n\nRECORDS:\n{data_json}',
        "verify": _verify_extract_names,
        "data_case": "people-records",
    },
    "dedup-count": {
        "bricks_task": "Given a list of integers under inputs.values, count how many distinct values it contains, return {\"unique_count\": N}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of integers, count distinct values. ONLY {{"unique_count": N}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_dedup_count,
        "data_case": "numbers-with-dups",
    },
    "sort-asc-unique": {
        "bricks_task": "Given a list of integers under inputs.values, deduplicate then sort ascending, return {\"unique_sorted\": [...]}.",
        "bricks_input_key": "values",
        "raw_llm_prompt": 'Given a JSON array of integers, dedupe and sort ascending. ONLY {{"unique_sorted": [...]}}.\n\nVALUES:\n{data_json}',
        "verify": _verify_sort_asc_full,
        "data_case": "numbers-with-dups",
    },
    "numeric-stats": {
        "bricks_task": (
            "Given a list of numbers under inputs.values, return a dict with "
            "keys sum, mean, min, max, count. sum is the arithmetic sum, mean "
            "is sum divided by count, min and max are the smallest and largest "
            "values, count is the number of values. All as numbers."
        ),
        "bricks_input_key": "values",
        "raw_llm_prompt": (
            "You are given a JSON array of numbers.\n\n"
            "Return ONLY a JSON object with exactly these keys:\n"
            "  sum: arithmetic sum of all values (number)\n"
            "  mean: sum divided by count (number)\n"
            "  min: smallest value (number)\n"
            "  max: largest value (number)\n"
            "  count: number of values (integer)\n\n"
            "Output only the JSON, no prose, no code fences.\n\n"
            "VALUES:\n{data_json}"
        ),
        "verify": _numeric_stats_verify,
    },
}


# ─── Meta ────────────────────────────────────────────────────────────────────


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def _pip_freeze_hash() -> str:
    out = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    return "sha256:" + hashlib.sha256(out.encode()).hexdigest()


# ─── Raw-LLM parse helper ────────────────────────────────────────────────────


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Best-effort JSON parse of a raw-LLM response.

    LLMs sometimes wrap output in ``` fences despite being told not to.
    Strip the common wrappers; if it's still not JSON, surface the raw text
    and let the verifier record it as incorrect rather than crashing the run.
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        # drop optional language tag line
        s = s.removeprefix("json").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {"__parse_error__": True, "raw": text}


# ─── Engine runners ──────────────────────────────────────────────────────────


PROVIDER_TIMEOUT_S = 600  # compose can take minutes on realistic catalogs; raw default 120s was too short


def _run_bricks(case: dict[str, Any], data: list[str], model: str) -> dict[str, Any]:
    # Capture Bricks' own cache-hit logging so we can prove store vs prompt-cache.
    import logging as _logging
    log_buf = io.StringIO()
    log_handler = _logging.StreamHandler(log_buf)
    log_handler.setLevel(_logging.INFO)
    log_handler.setFormatter(_logging.Formatter("%(name)s %(levelname)s %(message)s"))
    _logging.getLogger("bricks").addHandler(log_handler)
    _logging.getLogger("bricks").setLevel(_logging.INFO)

    wrapped = AccumulatingProvider(ClaudeCodeProvider(model=model, timeout=PROVIDER_TIMEOUT_S))
    engine = Bricks.default(provider=wrapped)
    t0 = time.perf_counter()
    err: str | None = None
    outputs: dict[str, Any] = {}
    blueprint_yaml = ""
    cache_hit: bool | None = None
    api_calls_engine: int | None = None
    try:
        result = engine.execute(
            task=case["bricks_task"],
            inputs={case["bricks_input_key"]: data},
            verbose=True,
        )
        outputs = result.get("outputs", {})
        blueprint_yaml = result.get("blueprint_yaml", "") or ""
        cache_hit = result.get("cache_hit")
        api_calls_engine = result.get("api_calls")
    except Exception as e:  # noqa: BLE001 — we want any failure captured, not crashed
        import traceback as _tb
        err = f"{type(e).__name__}: {e}\n{_tb.format_exc()}"
    finally:
        _logging.getLogger("bricks").removeHandler(log_handler)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    totals = wrapped.totals()
    log_text = log_buf.getvalue()
    bricks_log_lines = [ln for ln in log_text.splitlines() if "cache hit" in ln.lower() or "composing blueprint" in ln.lower()]
    return {
        "success": err is None,
        "error": err,
        "outputs": outputs,
        "tokens": {
            "input": totals["input"],
            "output": totals["output"],
            "cache_read": totals["cache_read"],
            "cache_creation": totals["cache_creation"],
        },
        "cost_usd": totals["cost_usd"],
        "duration_ms": duration_ms,
        "blueprint_yaml": blueprint_yaml,
        "n_llm_calls": totals["n_calls"],
        "tokens_estimated": totals["any_estimated"],
        "engine_cache_hit": cache_hit,
        "engine_api_calls": api_calls_engine,
        "bricks_log_signals": bricks_log_lines,
    }


def _run_raw_llm(case: dict[str, Any], data: list[str], model: str) -> dict[str, Any]:
    provider = ClaudeCodeProvider(model=model, timeout=PROVIDER_TIMEOUT_S)
    prompt = case["raw_llm_prompt"].format(data_json=json.dumps(data))
    t0 = time.perf_counter()
    err: str | None = None
    parsed: dict[str, Any] = {}
    res: CompletionResult | None = None
    try:
        res = provider.complete(prompt)
        parsed = _parse_llm_json(res.text)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "success": err is None and "__parse_error__" not in parsed,
        "error": err,
        "outputs": parsed,
        "tokens": {
            "input": res.input_tokens if res else 0,
            "output": res.output_tokens if res else 0,
            "cache_read": res.cached_input_tokens if res else 0,
            "cache_creation": res.cache_creation_input_tokens if res else 0,
        },
        "cost_usd": res.cost_usd if res else 0.0,
        "duration_ms": duration_ms,
        "tokens_estimated": res.estimated if res else False,
    }


# ─── Orchestration ───────────────────────────────────────────────────────────


def run_case(case_slug: str, size: int, model: str, notes: str = "") -> Path:
    case = CASES[case_slug]
    data_slug = case.get("data_case", case_slug)
    data_path = CASES_DIR / data_slug / f"data-{size}.json"
    truth_path = CASES_DIR / data_slug / f"data-{size}.truth.json"
    if not data_path.exists() or not truth_path.exists():
        raise FileNotFoundError(
            f"Missing data or truth for {case_slug} size={size}. "
            f"Run: python cases/{case_slug}/generate.py {size}"
        )
    data = json.loads(data_path.read_text())
    truth = json.loads(truth_path.read_text())

    bricks_out = _run_bricks(case, data, model)
    raw_out = _run_raw_llm(case, data, model)

    def _v(out: dict[str, Any]) -> dict[str, Any]:
        try:
            return case["verify"](out, truth, data=data)
        except TypeError:
            return case["verify"](out, truth)

    bricks_verdict = _v(bricks_out["outputs"]) if bricks_out["success"] else {"correct": False, "per_field_diffs": []}
    raw_verdict = _v(raw_out["outputs"]) if raw_out["success"] else {"correct": False, "per_field_diffs": []}

    run_id = str(uuid.uuid4())
    record = {
        "run_id": run_id,
        "track": TRACK,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "git_sha": _git_sha(),
            "pip_freeze_hash": _pip_freeze_hash(),
            "model": model,
            "seed": 42,
            "runner": RUNNER_REL,
        },
        "config": {"case_slug": case_slug, "data_size": size},
        "bricks": {
            "success": bricks_out["success"],
            "error": bricks_out["error"],
            "outputs": bricks_out["outputs"],
            "tokens": bricks_out["tokens"],
            "cost_usd": bricks_out["cost_usd"],
            "duration_ms": bricks_out["duration_ms"],
            "blueprint_yaml": bricks_out["blueprint_yaml"],
            "n_llm_calls": bricks_out["n_llm_calls"],
            "tokens_estimated": bricks_out["tokens_estimated"],
            "engine_cache_hit": bricks_out.get("engine_cache_hit"),
            "engine_api_calls": bricks_out.get("engine_api_calls"),
            "bricks_log_signals": bricks_out.get("bricks_log_signals", []),
        },
        "raw_llm": {
            "success": raw_out["success"],
            "error": raw_out["error"],
            "outputs": raw_out["outputs"],
            "tokens": raw_out["tokens"],
            "cost_usd": raw_out["cost_usd"],
            "duration_ms": raw_out["duration_ms"],
            "tokens_estimated": raw_out["tokens_estimated"],
        },
        "verdict": {
            "bricks_correct": bricks_verdict["correct"],
            "raw_llm_correct": raw_verdict["correct"],
            "bricks_per_field_diffs": bricks_verdict["per_field_diffs"],
            "raw_llm_per_field_diffs": raw_verdict["per_field_diffs"],
        },
        "notes": notes,
    }

    run_path = RUNS_DIR / f"{TRACK}_{run_id}.json"
    run_path.write_text(json.dumps(record, indent=2))

    manifest_line = {
        "run_id": run_id,
        "track": TRACK,
        "timestamp": record["timestamp"],
        "git_sha": record["meta"]["git_sha"],
        "model": model,
        "case_slug": case_slug,
        "data_size": size,
        "bricks_correct": record["verdict"]["bricks_correct"],
        "raw_llm_correct": record["verdict"]["raw_llm_correct"],
        "bricks_cost_usd": record["bricks"]["cost_usd"],
        "raw_llm_cost_usd": record["raw_llm"]["cost_usd"],
        "bricks_input_tokens": record["bricks"]["tokens"]["input"],
        "bricks_output_tokens": record["bricks"]["tokens"]["output"],
        "bricks_cache_read": record["bricks"]["tokens"]["cache_read"],
        "bricks_cache_creation": record["bricks"]["tokens"]["cache_creation"],
        "raw_llm_input_tokens": record["raw_llm"]["tokens"]["input"],
        "raw_llm_output_tokens": record["raw_llm"]["tokens"]["output"],
        "bricks_duration_ms": record["bricks"]["duration_ms"],
        "raw_llm_duration_ms": record["raw_llm"]["duration_ms"],
        "bricks_n_llm_calls": record["bricks"]["n_llm_calls"],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest_line) + "\n")

    return run_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Track 1 exploration runner")
    ap.add_argument("--case", required=True, choices=sorted(CASES.keys()))
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--model", default="sonnet", help="Claude Code model alias (sonnet|haiku|opus or full id)")
    ap.add_argument("--notes", default="", help="Free-text notes recorded in the run file")
    args = ap.parse_args()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = run_case(args.case, args.size, args.model, args.notes)
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
