from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from tests.benchmarks.test_import_benchmark import benchmark_import

if TYPE_CHECKING:
    from collections.abc import Callable

RUN_IMPORT = "tests.benchmarks.test_import_benchmark.run_import"


class BenchmarkStandIn:
    r"""Stand in for the benchmark fixture.

    Args:
        num_runs: The number of times ``pedantic`` runs the function:
            1 with ``--benchmark-disable``.
    """

    def __init__(self, num_runs: int) -> None:
        self._num_runs = num_runs
        self.extra_info: dict[str, Any] = {}

    def pedantic(self, func: Callable[[], object], **_options: int) -> None:
        r"""Run ``func`` ``num_runs`` times, whatever the options."""
        for _ in range(self._num_runs):
            func()


######################################
#     Tests for benchmark_import     #
######################################


def test_benchmark_import_single_run() -> None:
    benchmark: Any = BenchmarkStandIn(num_runs=1)
    with patch(RUN_IMPORT, return_value={"seconds": 0.5, "num_modules": 20}):
        benchmark_import(benchmark, "pass")
    assert benchmark.extra_info == {
        "import_seconds_min": 0.5,
        "import_seconds_median": 0.5,
        "num_modules": 20,
    }


def test_benchmark_import_ignores_the_warm_up_run() -> None:
    benchmark: Any = BenchmarkStandIn(num_runs=4)
    results = [
        {"seconds": 0.1, "num_modules": 20},
        {"seconds": 0.5, "num_modules": 21},
        {"seconds": 0.3, "num_modules": 22},
        {"seconds": 0.4, "num_modules": 23},
    ]
    with patch(RUN_IMPORT, side_effect=results):
        benchmark_import(benchmark, "pass")
    assert benchmark.extra_info == {
        "import_seconds_min": 0.3,
        "import_seconds_median": 0.4,
        "num_modules": 23,
    }


def test_benchmark_import_runs_the_statement() -> None:
    benchmark: Any = BenchmarkStandIn(num_runs=1)
    with patch(RUN_IMPORT, return_value={"seconds": 0.5, "num_modules": 20}) as run_import:
        benchmark_import(benchmark, "import minevent")
    run_import.assert_called_once_with("import minevent")


def test_benchmark_import_failing_statement() -> None:
    benchmark: Any = BenchmarkStandIn(num_runs=1)
    with (
        patch(RUN_IMPORT, side_effect=RuntimeError("import failed")),
        pytest.raises(RuntimeError, match=r"import failed"),
    ):
        benchmark_import(benchmark, "import missing")
