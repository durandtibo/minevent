r"""Benchmarks for the import time of ``minevent``.

The import is measured in a fresh interpreter (``sys.modules`` caches the
imports, so an in-process measurement only sees the first import). Run the
benchmarks explicitly with:

    inv test.benchmark

The wall time of the subprocess includes the start of the interpreter, so
``test_python_startup_benchmark`` gives the baseline to subtract. The
``extra_info`` of each result, saved with the benchmark JSON, records the
import time measured inside the interpreter and the number of modules
loaded.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

CODE = """
import json, sys, time
start = time.perf_counter()
{statement}
elapsed = time.perf_counter() - start
print(json.dumps({{"seconds": elapsed, "num_modules": len(sys.modules)}}))
"""


def run_import(statement: str) -> dict[str, float]:
    r"""Run ``statement`` in a fresh isolated interpreter.

    Args:
        statement: The code to time.

    Returns:
        The time of the statement in seconds and the number of
            modules loaded.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", CODE.format(statement=statement)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def benchmark_import(benchmark: BenchmarkFixture, statement: str) -> None:
    r"""Benchmark ``statement`` and save the details in
    ``extra_info``."""
    results: list[dict[str, float]] = []
    benchmark.pedantic(
        lambda: results.append(run_import(statement)), rounds=10, warmup_rounds=1, iterations=1
    )
    seconds = [r["seconds"] for r in results[1:]]  # the first run is the warm-up
    benchmark.extra_info.update(
        {
            "import_seconds_min": min(seconds),
            "import_seconds_median": statistics.median(seconds),
            "num_modules": results[-1]["num_modules"],
        }
    )


def test_python_startup_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark_import(benchmark, "pass")


def test_import_minevent_benchmark(benchmark: BenchmarkFixture) -> None:
    benchmark_import(benchmark, "import minevent")
