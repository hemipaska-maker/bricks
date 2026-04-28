"""Generate numeric-stats data + ground truth.

Usage: python generate.py [size ...]
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
SIZES = [50, 200, 1000, 5000, 20000]
SEED = 42


def generate(size: int, seed: int = SEED) -> tuple[list[float], dict]:
    rng = random.Random(seed + size)
    # 60% uniform, 40% lognormal to give tails without being degenerate
    vals: list[float] = []
    for _ in range(size):
        if rng.random() < 0.6:
            vals.append(round(rng.uniform(0.0, 100.0), 4))
        else:
            vals.append(round(rng.lognormvariate(1.5, 0.8), 4))
    total = sum(vals)
    truth = {
        "sum": round(total, 6),
        "mean": round(total / size, 6),
        "min": round(min(vals), 6),
        "max": round(max(vals), 6),
        "count": size,
    }
    return vals, truth


def write(size: int) -> None:
    vals, truth = generate(size)
    (HERE / f"data-{size}.json").write_text(json.dumps(vals))
    (HERE / f"data-{size}.truth.json").write_text(json.dumps(truth, indent=2))
    print(f"wrote data-{size}.json ({size} values) + truth")


if __name__ == "__main__":
    targets = [int(x) for x in sys.argv[1:]] or SIZES
    for n in targets:
        write(n)
