#!/usr/bin/env python3
"""Times the Golden Gate design calculation of the Biologik engine.

Usage (from the project folder):

    python3 scripts/benchmark_design.py [runs]

Two cases are measured in the engine itself (without the web server):
  1. the worked example of the README (toolkit parts only, docs/examples/oxygen-free-space-request.json)
  2. the same construct with an own cargo of about 1.5 kb, which is codon optimized and checked for restriction sites
Each case runs `runs` times (default 20). The result is the median, the fastest and the slowest run in seconds.
"""

from __future__ import annotations

import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Biologik.level0_design.design import design_construct  # noqa: E402

EXAMPLE = json.loads((ROOT / "docs" / "examples" / "oxygen-free-space-request.json").read_text())


def own_cargo_request(length_codons: int = 500) -> dict:
    """The example with an own cargo: a random protein of the given length, entered as amino acids."""
    rng = random.Random(1)
    protein = "M" + "".join(rng.choice("ACDEFGHIKLMNPQRSTVWY") for _ in range(length_codons - 1))
    return {**EXAMPLE, "cargoLabel": "Own protein", "cargoSeq": protein}


def measure(request: dict, runs: int) -> list[float]:
    design_construct(request)  # warm-up: imports and the first read of the part files
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        design_construct(request)
        times.append(time.perf_counter() - start)
    return times


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"Python {platform.python_version()} on {platform.platform()}, {runs} runs per case")
    for name, request in (("README example (toolkit parts)", EXAMPLE), ("own cargo of 500 amino acids", own_cargo_request())):
        times = measure(request, runs)
        print(f"{name}: median {statistics.median(times):.2f} s, fastest {min(times):.2f} s, slowest {max(times):.2f} s")


if __name__ == "__main__":
    main()
