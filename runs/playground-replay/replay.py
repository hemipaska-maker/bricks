"""Replay every web-playground scenario via HTTP and persist the full RunResponse.

Drives the local /playground/run endpoint with compare=true and saves each
response to runs/playground-replay/<scenario_id>.json so we have a permanent
record. Intended for the playground "Bricks loses on all scenarios"
investigation at sha bf68452.

Usage:
    python runs/playground-replay/replay.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BASE = "http://localhost:8742"
OUT_DIR = Path(__file__).parent
PROVIDER = "claude_code"
MODEL = "sonnet"


def fetch_scenarios() -> list[dict]:
    r = requests.get(f"{BASE}/playground/scenarios", timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_detail(scenario_id: str) -> dict:
    # Try plural first (per schema doc), fall back to singular.
    for path in (f"/playground/scenarios/{scenario_id}", f"/playground/scenario/{scenario_id}"):
        r = requests.get(f"{BASE}{path}", timeout=10)
        if r.status_code == 200:
            return r.json()
    r.raise_for_status()
    return {}


def run_scenario(detail: dict) -> dict:
    body = {
        "provider": PROVIDER,
        "model": MODEL,
        "task": detail["task"],
        "data": detail["data"],
        "expected_output": detail.get("expected_output"),
        "compare": True,
    }
    t0 = time.monotonic()
    r = requests.post(f"{BASE}/playground/run", json=body, timeout=900)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return {
            "_http_status": r.status_code,
            "_http_body": r.text[:2000],
            "_driver_elapsed_ms": elapsed_ms,
        }
    out = r.json()
    out["_driver_elapsed_ms"] = elapsed_ms
    return out


def main() -> int:
    scenarios = fetch_scenarios()
    print(f"Fetched {len(scenarios)} scenarios")
    summary = []
    for s in scenarios:
        sid = s["id"]
        print(f"\n=== {sid} ===")
        try:
            detail = fetch_detail(sid)
        except Exception as exc:  # noqa: BLE001
            print(f"  detail-fetch failed: {exc}")
            continue
        try:
            result = run_scenario(detail)
        except requests.Timeout:
            result = {"_driver_error": "client timeout"}
        except Exception as exc:  # noqa: BLE001
            result = {"_driver_error": f"{type(exc).__name__}: {exc}"}

        path = OUT_DIR / f"{sid}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump({"scenario": detail, "result": result}, fh, indent=2)

        b = (result.get("bricks") or {}) if isinstance(result, dict) else {}
        r_ = (result.get("raw_llm") or {}) if isinstance(result, dict) else {}
        b_err = b.get("error") or ""
        b_outs = b.get("outputs") or {}
        r_outs = r_.get("outputs") or {}
        b_dsl_present = bool(b.get("dsl_code"))
        r_err = r_.get("error") or ""
        print(f"  bricks: error={b_err!r:.80} outputs_keys={list(b_outs.keys())} dsl_present={b_dsl_present}")
        print(f"  rawllm: error={r_err!r:.80} outputs_keys={list(r_outs.keys())}")
        summary.append({
            "id": sid,
            "bricks_error": b_err[:300] if b_err else "",
            "bricks_outputs_keys": list(b_outs.keys()),
            "bricks_dsl_present": b_dsl_present,
            "raw_outputs_keys": list(r_outs.keys()),
            "raw_error": r_err[:200] if r_err else "",
            "elapsed_ms": result.get("_driver_elapsed_ms") if isinstance(result, dict) else None,
        })

    (OUT_DIR / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nWrote per-scenario JSON + _summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
