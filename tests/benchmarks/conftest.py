r"""Skip the benchmarks unless they are explicitly requested.

The benchmarks take several seconds, so they are not run with the other
tests. Run them with ``inv test.benchmark`` (``--benchmark-only``).
``--benchmark-disable`` runs each benchmark once, without measure, to
check that it still works.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    r"""Skip the benchmarks if neither ``--benchmark-only`` nor
    ``--benchmark-disable`` is given.

    Args:
        config: The pytest configuration.
        items: The collected tests.
    """
    if config.getoption("benchmark_only") or config.getoption("benchmark_disable"):
        return
    skip = pytest.mark.skip(reason="benchmarks only run with --benchmark-only")
    for item in items:
        if "tests/benchmarks" in item.nodeid:
            item.add_marker(skip)
