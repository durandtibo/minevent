r"""Benchmarks for reading the context of a trigger.

Run them explicitly with:

    inv test.benchmark
"""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING

import pytest

from minevent import Context

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def make_context(num_keys: int) -> Context:
    r"""Create a context with ``num_keys`` keys named ``key_<i>``."""
    return Context({f"key_{i}": i for i in range(num_keys)})


@pytest.mark.parametrize("num_keys", [1, 100])
@pytest.mark.parametrize("key", ["key_0", "missing"])
def test_context_get_benchmark(benchmark: BenchmarkFixture, num_keys: int, key: str) -> None:
    benchmark(make_context(num_keys).get, key)


@pytest.mark.parametrize("num_keys", [1, 100])
@pytest.mark.parametrize("key", ["key_0", "missing"])
def test_context_contains_benchmark(benchmark: BenchmarkFixture, num_keys: int, key: str) -> None:
    benchmark(operator.contains, make_context(num_keys), key)
