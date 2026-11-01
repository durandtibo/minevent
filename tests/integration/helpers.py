from __future__ import annotations

__all__ = ["run_threads"]

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def run_threads(func: Callable[[int], None], num_threads: int = 8) -> None:
    r"""Run a function in several threads that start at the same time.

    Args:
        func: The function to run. It takes the index of the thread.
        num_threads: The number of threads.

    Raises:
        RuntimeError: if a thread raised an exception.
    """
    barrier = threading.Barrier(num_threads)
    errors: list[BaseException] = []

    def target(index: int) -> None:
        try:
            barrier.wait()
            func(index)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=target, args=(i,)) for i in range(num_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        msg = f"{len(errors)} thread(s) raised an exception: {errors[0]!r}"
        raise RuntimeError(msg) from errors[0]
