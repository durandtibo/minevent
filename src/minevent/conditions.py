r"""Implement some conditions that can be used in the event system.

A condition is any function without argument that returns a boolean, see
the ``Condition`` protocol. The conditions of this module keep a state
between calls.
"""

from __future__ import annotations

__all__ = ["AfterNCondition", "Condition", "OnceCondition", "PeriodicCondition"]

from typing import Protocol


class Condition(Protocol):
    r"""Define the protocol of a condition for ``EventHandler``.

    A condition is any function without argument that returns a
    boolean: a lambda, a method, or an object with a ``__call__``
    method like the conditions of this module. It is called each time
    the event is triggered, before the handler, and the handler is
    executed only if it returns ``True``. A condition can keep a state
    between calls.

    To combine conditions, write a function. The function decides
    which conditions are evaluated: ``lambda: a() and b()`` skips ``b``
    when ``a`` is ``False``, while ``lambda: all([a(), b()])``
    evaluates both, so stateful conditions advance together.

    Example:
        ```pycon
        >>> from minevent import EventHandler, PeriodicCondition
        >>> condition = PeriodicCondition(freq=3)
        >>> handler = EventHandler(print, ["Hello!"], condition=condition)
        >>> handler.handle()
        Hello!
        >>> handler.handle()
        >>> handler = EventHandler(print, ["Bye!"], condition=lambda: False)
        >>> handler.handle()

        ```
    """

    def __call__(self) -> bool:
        r"""Evaluate the condition given the current state.

        Returns:
            ``True`` if the event handler should be executed,
                otherwise ``False``.
        """


class PeriodicCondition:
    r"""Implement a periodic condition.

    This condition evaluates to ``True`` on the first call and then every ``freq`` calls. It
    maintains an internal counter that increments with each call. The condition is ``True`` when
    the counter modulo ``freq`` equals zero.

    Note that a call is not idempotent: each call advances the
    counter, so the condition is stateful. Do not share one instance
    between several handlers, because they would advance the same
    counter. Use ``reset`` to restart the counter. The counter is not
    protected by a lock, so a condition should be called from one
    thread.

    Args:
        freq: The frequency (interval) at which the condition
            evaluates to ``True``. Must be a positive integer.
        skip_first: If ``True``, the first call evaluates to
            ``False``, and then the condition evaluates to ``True``
            every ``freq`` calls. Default is ``False``.

    Raises:
        TypeError: if ``freq`` is not an integer.
        ValueError: if ``freq`` is lower than 1.

    Example:
        ```pycon
        >>> from minevent import PeriodicCondition
        >>> condition = PeriodicCondition(freq=3)
        >>> [condition() for _ in range(7)]
        [True, False, False, True, False, False, True]
        >>> condition = PeriodicCondition(freq=2, skip_first=True)
        >>> [condition() for _ in range(3)]
        [False, False, True]

        ```
    """

    def __init__(self, freq: int, *, skip_first: bool = False) -> None:
        if isinstance(freq, bool) or not isinstance(freq, int):
            msg = f"freq must be an integer, got {type(freq).__qualname__}"
            raise TypeError(msg)
        if freq < 1:
            msg = f"freq must be greater than or equal to 1, got {freq}"
            raise ValueError(msg)
        self._freq = freq
        self._skip_first = bool(skip_first)
        self._step = 0

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}(freq={self._freq:,}, "
            f"skip_first={self._skip_first}, step={self._step:,})"
        )

    def __call__(self) -> bool:
        condition = self._step % self._freq == 0 and not (self._skip_first and self._step == 0)
        self._step += 1
        return condition

    @property
    def freq(self) -> int:
        r"""Get the frequency of the periodic condition.

        Returns:
            The number of calls between each ``True`` result. The
                condition evaluates to ``True`` every ``freq`` calls.
        """
        return self._freq

    @property
    def skip_first(self) -> bool:
        r"""Indicate if the first call is skipped.

        Returns:
            ``True`` if the first call returns ``False``, otherwise
                ``False``.
        """
        return self._skip_first

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
        self._step = 0


class OnceCondition:
    r"""Implement a condition that is ``True`` only on the first call.

    The handler stays registered and is skipped afterwards. Use
    ``once=True`` in ``EventManager.add_event_handler`` to remove the
    registration instead. The condition is stateful, like
    ``PeriodicCondition``.

    Example:
        ```pycon
        >>> from minevent import OnceCondition
        >>> condition = OnceCondition()
        >>> condition(), condition()
        (True, False)

        ```
    """

    def __init__(self) -> None:
        self._done = False

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(done={self._done})"

    def __call__(self) -> bool:
        condition = not self._done
        self._done = True
        return condition


class AfterNCondition:
    r"""Implement a condition that is ``False`` for the first ``n``
    calls and ``True`` afterwards.

    The condition is stateful, like ``PeriodicCondition``.

    Args:
        n: The number of calls to skip. Must be a non-negative
            integer.

    Raises:
        TypeError: if ``n`` is not an integer.
        ValueError: if ``n`` is negative.

    Example:
        ```pycon
        >>> from minevent import AfterNCondition
        >>> condition = AfterNCondition(2)
        >>> [condition() for _ in range(4)]
        [False, False, True, True]

        ```
    """

    def __init__(self, n: int) -> None:
        if isinstance(n, bool) or not isinstance(n, int):
            msg = f"n must be an integer, got {type(n).__qualname__}"
            raise TypeError(msg)
        if n < 0:
            msg = f"n must be greater than or equal to 0, got {n}"
            raise ValueError(msg)
        self._n = n
        self._step = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(n={self._n:,}, step={self._step:,})"

    def __call__(self) -> bool:
        condition = self._step >= self._n
        self._step += 1
        return condition

    @property
    def n(self) -> int:
        r"""Get the number of skipped calls.

        Returns:
            The number of calls that evaluate to ``False``.
        """
        return self._n
