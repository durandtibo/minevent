r"""Implement the conditions that can be used in the event system.

A condition is any synchronous function that returns a boolean (a
lambda, a method or a callable object). It is called before its handler,
like a handler: as ``condition()``, or as ``condition(context)`` with
the read-only ``Context`` of the trigger (see
``minevent.calls.adapt_call``). ``Condition`` is its type, and
``EventManager.add_event_handler`` states how a registration uses it.
``PeriodicCondition`` counts its calls. The user guide of the
documentation shows how to combine conditions.

Example:
    ```pycon
    >>> from minevent import EventManager, PeriodicCondition
    >>> manager = EventManager()
    >>> _ = manager.add_event_handler(
    ...     "hello", lambda: print("Hello!"), condition=PeriodicCondition(freq=3)
    ... )
    >>> manager.trigger_event("hello")
    Hello!
    >>> manager.trigger_event("hello")
    >>> _ = manager.add_event_handler("bye", lambda: print("Bye!"), condition=lambda: False)
    >>> manager.trigger_event("bye")
    >>> _ = manager.add_event_handler(
    ...     "epoch_end",
    ...     lambda: print("late epoch"),
    ...     condition=lambda context: context.get("epoch", 0) >= 2,
    ... )
    >>> manager.trigger_event("epoch_end", {"epoch": 1})
    >>> manager.trigger_event("epoch_end", {"epoch": 2})
    late epoch

    ```
"""

from __future__ import annotations

__all__ = ["Condition", "PeriodicCondition"]

import reprlib
import threading
from collections.abc import Callable

from minevent.context import Context

Condition = Callable[[], bool] | Callable[[Context], bool]
"""A condition: a function that returns a boolean, without parameter or
with the ``Context`` of the trigger."""


class PeriodicCondition:
    r"""Implement a periodic condition.

    This condition evaluates to ``True`` on one call in ``freq``, from the call of index
    ``start`` (the first call has the index 0). It maintains an internal counter that increments
    with each call. The condition is ``True`` when the counter minus ``start`` is not negative and
    is a multiple of ``freq``. With ``freq=3``, ``start=0`` is ``True`` on the calls 0, 3 and 6,
    ``start=3`` skips the first call (3, 6 and 9), and ``start=2`` is ``True`` at the end of every
    third call (2, 5 and 8). With ``freq=1``, it is a warm-up: ``False`` for the first ``start``
    calls and ``True`` afterwards.

    Note that a call is not idempotent: each call advances the
    counter, so the condition is stateful. Do not share one instance
    between several handlers, because they would advance the same
    counter. Use ``reset`` to restart the counter.

    The counter is protected by a lock, so every call is counted once,
    from any number of threads, with and without the GIL. A lock cannot
    be copied or pickled: a copy of a condition (``copy.copy``,
    ``copy.deepcopy`` or ``pickle``) starts at the same step, and then
    has its own counter and lock.

    Args:
        freq: The frequency (interval) at which the condition
            evaluates to ``True``. Must be a positive integer.
        start: The index, from 0, of the first call that evaluates to
            ``True``. Must be a non-negative integer. Default is
            ``0``.

    Raises:
        TypeError: if ``freq`` or ``start`` is not an integer.
        ValueError: if ``freq`` is lower than 1, or if ``start`` is
            lower than 0.

    Example:
        ```pycon
        >>> from minevent import PeriodicCondition
        >>> condition = PeriodicCondition(freq=3)
        >>> [condition() for _ in range(7)]
        [True, False, False, True, False, False, True]
        >>> condition = PeriodicCondition(freq=3, start=2)
        >>> [condition() for _ in range(7)]
        [False, False, True, False, False, True, False]
        >>> condition = PeriodicCondition(freq=1, start=2)
        >>> [condition() for _ in range(4)]
        [False, False, True, True]
        >>> import copy
        >>> clone = copy.deepcopy(condition)
        >>> clone
        PeriodicCondition(freq=1, start=2, step=4)

        ```
    """

    def __init__(self, freq: int, *, start: int = 0) -> None:
        if isinstance(freq, bool) or not isinstance(freq, int):
            msg = f"freq must be an integer, got {type(freq).__qualname__}"
            raise TypeError(msg)
        if freq < 1:
            msg = f"freq must be greater than or equal to 1, got {reprlib.repr(freq)}"
            raise ValueError(msg)
        if isinstance(start, bool) or not isinstance(start, int):
            msg = f"start must be an integer, got {type(start).__qualname__}"
            raise TypeError(msg)
        if start < 0:
            msg = f"start must be greater than or equal to 0, got {reprlib.repr(start)}"
            raise ValueError(msg)
        self._freq = freq
        self._start = start
        self._step = 0
        self._lock = threading.Lock()

    def __getstate__(self) -> dict[str, object]:
        return {key: value for key, value in self.__dict__.items() if key != "_lock"}

    def __setstate__(self, state: dict[str, object]) -> None:
        self.__dict__.update(state)
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}(freq={self._freq}, "
            f"start={self._start}, step={self._step})"
        )

    def __call__(self) -> bool:
        with self._lock:
            step = self._step
            self._step = step + 1
        offset = step - self._start
        return offset >= 0 and offset % self._freq == 0

    @property
    def freq(self) -> int:
        r"""Get the frequency of the periodic condition.

        Returns:
            The number of calls between each ``True`` result. The
                condition evaluates to ``True`` every ``freq`` calls.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> PeriodicCondition(freq=3).freq
            3

            ```
        """
        return self._freq

    @property
    def start(self) -> int:
        r"""Get the index of the first call that is ``True``.

        Returns:
            The index, from 0, of the first call that evaluates to
                ``True``.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> PeriodicCondition(freq=3, start=2).start
            2

            ```
        """
        return self._start

    def reset(self) -> None:
        r"""Reset the internal counter, as if the condition was just
        created.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> condition = PeriodicCondition(freq=2)
            >>> condition(), condition()
            (True, False)
            >>> condition.reset()
            >>> condition()
            True

            ```
        """
        with self._lock:
            self._step = 0
