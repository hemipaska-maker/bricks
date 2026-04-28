"""Generate synthetic log-analysis data + ground truth.

Usage:
    python generate.py              # writes all default sizes
    python generate.py 1000         # writes just size=1000

Deterministic given seed. Ground truth is computed from the same source of
truth the generator uses, so verification is a plain file compare.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent

SIZES = [50, 200, 1000, 5000, 20000]
SEED = 42

SEVERITY_WEIGHTS = [("INFO", 0.80), ("WARN", 0.12), ("ERROR", 0.07), ("DEBUG", 0.01)]

SERVICES = [
    "api-gateway", "auth-service", "order-service", "payment-service",
    "inventory-service", "notification-service", "search-service",
]

INFO_MESSAGES = [
    "Request completed in {ms}ms",
    "User {uid} logged in",
    "Cache hit for key {key}",
    "Health check OK",
    "Background job finished",
]

WARN_MESSAGES = [
    "Slow query took {ms}ms",
    "Retrying request (attempt {n})",
    "Deprecated endpoint used by {uid}",
    "Cache miss rate elevated",
]

# Zipf-ish: first template dominates. Top-3 after sampling is stable.
ERROR_TEMPLATES = [
    "Connection refused to upstream",          # weight 30
    "Timeout after 30s calling /api/users",    # weight 18
    "Null pointer in OrderService.process",    # weight 12
    "Database deadlock on orders table",       # weight 8
    "Rate limit exceeded for client",          # weight 6
    "Invalid JWT signature",                   # weight 5
    "S3 upload failed: access denied",         # weight 4
    "Payment gateway returned 502",            # weight 3
    "Disk usage above 90% on /var",            # weight 2
    "Kafka consumer lag exceeded threshold",   # weight 2
    "Memory allocation failed",                # weight 1
    "Unknown error in notification worker",    # weight 1
]
ERROR_WEIGHTS = [30, 18, 12, 8, 6, 5, 4, 3, 2, 2, 1, 1]

DEBUG_MESSAGES = ["Trace span opened", "Span closed", "Debug flag active"]


def _weighted_pick(rng: random.Random, options: list[str], weights: list[float]) -> str:
    return rng.choices(options, weights=weights, k=1)[0]


def _pick_severity(rng: random.Random) -> str:
    return rng.choices(
        [s for s, _ in SEVERITY_WEIGHTS],
        weights=[w for _, w in SEVERITY_WEIGHTS],
        k=1,
    )[0]


def _render_message(rng: random.Random, severity: str) -> str:
    if severity == "INFO":
        tmpl = rng.choice(INFO_MESSAGES)
    elif severity == "WARN":
        tmpl = rng.choice(WARN_MESSAGES)
    elif severity == "ERROR":
        return _weighted_pick(rng, ERROR_TEMPLATES, ERROR_WEIGHTS)
    else:
        tmpl = rng.choice(DEBUG_MESSAGES)
    return tmpl.format(
        ms=rng.randint(5, 4000),
        uid=f"u{rng.randint(1000, 9999)}",
        key=f"k{rng.randint(1, 500)}",
        n=rng.randint(1, 5),
    )


def _format_line(rng: random.Random, ts: datetime, severity: str, service: str, msg: str) -> str:
    line = f"{ts.isoformat()} {severity} {service} - {msg}"
    # 5% noise: extra whitespace or lowercase severity
    roll = rng.random()
    if roll < 0.03:
        line = line.replace(" ", "  ", 1)
    elif roll < 0.05:
        line = line.replace(severity, severity.lower(), 1)
    return line


def generate(size: int, seed: int = SEED) -> tuple[list[str], dict]:
    rng = random.Random(seed + size)  # different seed per size, reproducible
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    lines: list[str] = []
    severity_counts: Counter[str] = Counter({s: 0 for s, _ in SEVERITY_WEIGHTS})
    error_messages: Counter[str] = Counter()

    n_malformed = max(1, size // 100)  # ~1%
    malformed_indices = set(rng.sample(range(size), n_malformed))

    for i in range(size):
        ts += timedelta(milliseconds=rng.randint(10, 5000))
        if i in malformed_indices:
            lines.append(f"{ts.isoformat()} -- malformed fragment {i}")
            continue
        severity = _pick_severity(rng)
        service = rng.choice(SERVICES)
        msg = _render_message(rng, severity)
        lines.append(_format_line(rng, ts, severity, service, msg))
        severity_counts[severity] += 1
        if severity == "ERROR":
            error_messages[msg] += 1

    top3 = sorted(error_messages.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    truth = {
        "severity_counts": dict(severity_counts),
        "top_error_patterns": [{"pattern": p, "count": c} for p, c in top3],
    }
    return lines, truth


def write(size: int) -> None:
    lines, truth = generate(size)
    (HERE / f"data-{size}.json").write_text(json.dumps(lines, indent=2))
    (HERE / f"data-{size}.truth.json").write_text(json.dumps(truth, indent=2))
    print(f"wrote data-{size}.json ({len(lines)} lines) + truth")


if __name__ == "__main__":
    targets = [int(x) for x in sys.argv[1:]] or SIZES
    for n in targets:
        write(n)
