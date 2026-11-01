r"""Implement some conditions that can be used in the event system."""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "AlwaysCondition",
    "AndCondition",
    "BaseCondition",
    "CallableCondition",
    "NotCondition",
    "OnceCondition",
    "OrCondition",
    "PeriodicCondition",
    "as_condition",
]

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from coola.equality import objects_are_equal

if TYPE_CHECKING:
    from collections.abc import Callable


class BaseCondition(ABC):  # noqa: PLW1641
    r"""Define the base class to implement a condition for
    ``EventHandler``.

    A child class has to implement the following methods:

        - ``evaluate``
        - ``equal``

    ``equal`` is the primary comparison API and ``==`` delegates to
    it. Conditions are intentionally unhashable, like the event
    handlers.

    Example:
        ```pycon
        >>> from minevent import PeriodicCondition
        >>> condition = PeriodicCondition(freq=3)
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True

        ```
    """

    def __eq__(self, other: object) -> bool:
        return self.equal(other)

    @abstractmethod
    def equal(self, other: object) -> bool:
        r"""Compare two conditions for equality.

        This method should be implemented by child classes to define
        how conditions are compared. This is used when comparing
        conditional event handlers.

        Args:
            other: The other object to compare with. Can be any type,
                though typically a condition.

        Returns:
            ``True`` if the two conditions are considered equal,
                otherwise ``False``.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> condition = PeriodicCondition(freq=3)
            >>> condition.equal(PeriodicCondition(freq=3))
            True
            >>> condition.equal(PeriodicCondition(freq=2))
            False

            ```
        """

    @abstractmethod
    def evaluate(self) -> bool:
        r"""Evaluate the condition given the current state.

        This method should be implemented by child classes to define
        the logic for determining whether a conditional event handler
        should be executed. The method is called without arguments and
        may maintain internal state between calls.

        Returns:
            ``True`` if the condition is satisfied and the event
                handler logic should be executed, otherwise ``False``.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> condition = PeriodicCondition(freq=2)
            >>> condition.evaluate()
            True
            >>> condition.evaluate()
            False

            ```
        """


class PeriodicCondition(BaseCondition):
    r"""Implement a periodic condition.

    This condition evaluates to ``True`` on the first call and then every ``freq`` calls to the
    ``evaluate`` method. It maintains an internal counter that
    increments with each evaluation. The condition is ``True`` when
    the counter modulo ``freq`` equals zero.

    Note that ``evaluate`` is not idempotent: each call advances the
    counter, so the condition is stateful. Do not share one instance
    between several handlers, because they would advance the same
    counter. Use ``reset`` to restart the counter. Two conditions are
    equal if they have the same ``freq`` and ``skip_first``; the
    current progress is ignored, so duplicate handlers are detected
    whatever their progress.

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
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True
        >>> condition = PeriodicCondition(freq=2, skip_first=True)
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True

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

    @property
    def freq(self) -> int:
        r"""Get the frequency of the periodic condition.

        Returns:
            The number of evaluations between each ``True`` result.
                The condition evaluates to ``True`` every ``freq``
                calls.
        """
        return self._freq

    @property
    def skip_first(self) -> bool:
        r"""Indicate if the first evaluation is skipped.

        Returns:
            ``True`` if the first call to ``evaluate`` returns
                ``False``, otherwise ``False``.
        """
        return self._skip_first

    def equal(self, other: object) -> bool:
        if isinstance(other, PeriodicCondition):
            return self.freq == other.freq and self.skip_first == other.skip_first
        return False

    def evaluate(self) -> bool:
        condition = self._step % self._freq == 0 and not (self._skip_first and self._step == 0)
        self._step += 1
        return condition

    def reset(self) -> None:
        r"""Reset the internal counter, as if the condition was just
        created.

        Example:
            ```pycon
            >>> from minevent import PeriodicCondition
            >>> condition = PeriodicCondition(freq=2)
            >>> condition.evaluate()
            True
            >>> condition.evaluate()
            False
            >>> condition.reset()
            >>> condition.evaluate()
            True

            ```
        """
        self._step = 0


class CallableCondition(BaseCondition):
    r"""Wrap a function without argument that returns a boolean as a
    condition.

    Two callable conditions are equal if their functions are equal.

    Args:
        func: The function called by ``evaluate``. It takes no
            argument and returns a boolean.

    Raises:
        TypeError: if ``func`` is not callable.

    Example:
        ```pycon
        >>> from minevent import CallableCondition
        >>> condition = CallableCondition(lambda: True)
        >>> condition.evaluate()
        True

        ```
    """

    def __init__(self, func: Callable[[], bool]) -> None:
        if not callable(func):
            msg = f"func is not callable: {func}"
            raise TypeError(msg)
        self._func = func

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(func={self._func!r})"

    @property
    def func(self) -> Callable[[], bool]:
        r"""Get the wrapped function.

        Returns:
            The function called by ``evaluate``.
        """
        return self._func

    def equal(self, other: object) -> bool:
        if isinstance(other, CallableCondition):
            return objects_are_equal(self._func, other.func)
        return False

    def evaluate(self) -> bool:
        return bool(self._func())


def as_condition(condition: BaseCondition | Callable[[], bool]) -> BaseCondition:
    r"""Convert a condition or a function to a condition.

    Args:
        condition: A condition, or a function without argument that
            returns a boolean.

    Returns:
        ``condition`` if it is a ``BaseCondition``, otherwise a
            ``CallableCondition`` that wraps it.

    Raises:
        TypeError: if ``condition`` is neither a ``BaseCondition``
            nor callable.

    Example:
        ```pycon
        >>> from minevent import PeriodicCondition, as_condition
        >>> as_condition(PeriodicCondition(2))
        PeriodicCondition(freq=2, skip_first=False, step=0)
        >>> as_condition(lambda: True).evaluate()
        True

        ```
    """
    if isinstance(condition, BaseCondition):
        return condition
    if callable(condition):
        return CallableCondition(condition)
    msg = f"condition must be a BaseCondition or a callable, got {type(condition).__qualname__}"
    raise TypeError(msg)


class AlwaysCondition(BaseCondition):
    r"""Implement a condition that is always ``True``.

    Example:
        ```pycon
        >>> from minevent import AlwaysCondition
        >>> condition = AlwaysCondition()
        >>> condition.evaluate()
        True

        ```
    """

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}()"

    def equal(self, other: object) -> bool:
        return isinstance(other, AlwaysCondition)

    def evaluate(self) -> bool:
        return True


class OnceCondition(BaseCondition):
    r"""Implement a condition that is ``True`` only on the first call.

    The condition is stateful, like ``PeriodicCondition``: the
    progress is ignored by ``equal``.

    Example:
        ```pycon
        >>> from minevent import OnceCondition
        >>> condition = OnceCondition()
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        False

        ```
    """

    def __init__(self) -> None:
        self._done = False

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(done={self._done})"

    def equal(self, other: object) -> bool:
        return isinstance(other, OnceCondition)

    def evaluate(self) -> bool:
        condition = not self._done
        self._done = True
        return condition


class AfterNCondition(BaseCondition):
    r"""Implement a condition that is ``False`` for the first ``n``
    calls and ``True`` afterwards.

    The condition is stateful, like ``PeriodicCondition``: the
    progress is ignored by ``equal``.

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
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True
        >>> condition.evaluate()
        True

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

    @property
    def n(self) -> int:
        r"""Get the number of skipped calls.

        Returns:
            The number of calls that evaluate to ``False``.
        """
        return self._n

    def equal(self, other: object) -> bool:
        if isinstance(other, AfterNCondition):
            return self._n == other.n
        return False

    def evaluate(self) -> bool:
        condition = self._step >= self._n
        self._step += 1
        return condition


class _CombinedCondition(BaseCondition):
    r"""Define the base class of the conditions that combine other
    conditions.

    All the conditions are evaluated at each call, with no
    short-circuit, so stateful conditions advance consistently.

    Args:
        *conditions: The conditions to combine. Functions without
            argument that return a boolean are accepted.

    Raises:
        ValueError: if no condition is given.
        TypeError: if a condition is neither a ``BaseCondition`` nor
            callable.
    """

    def __init__(self, *conditions: BaseCondition | Callable[[], bool]) -> None:
        if not conditions:
            msg = f"{self.__class__.__qualname__} requires at least one condition"
            raise ValueError(msg)
        self._conditions = tuple(as_condition(condition) for condition in conditions)

    def __repr__(self) -> str:
        args = ", ".join(repr(condition) for condition in self._conditions)
        return f"{self.__class__.__qualname__}({args})"

    @property
    def conditions(self) -> tuple[BaseCondition, ...]:
        r"""Get the combined conditions.

        Returns:
            The conditions, in the order they were given.
        """
        return self._conditions

    def equal(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return objects_are_equal(self._conditions, other.conditions)


class AndCondition(_CombinedCondition):
    r"""Implement a condition that is ``True`` if all the conditions
    are ``True``.

    Args:
        *conditions: The conditions to combine. Functions without
            argument that return a boolean are accepted.

    Raises:
        ValueError: if no condition is given.
        TypeError: if a condition is neither a ``BaseCondition`` nor
            callable.

    Example:
        ```pycon
        >>> from minevent import AndCondition, AfterNCondition, PeriodicCondition
        >>> condition = AndCondition(AfterNCondition(1), PeriodicCondition(2))
        >>> [condition.evaluate() for _ in range(5)]
        [False, False, True, False, True]

        ```
    """

    def evaluate(self) -> bool:
        results = [condition.evaluate() for condition in self._conditions]
        return all(results)


class OrCondition(_CombinedCondition):
    r"""Implement a condition that is ``True`` if at least one
    condition is ``True``.

    Args:
        *conditions: The conditions to combine. Functions without
            argument that return a boolean are accepted.

    Raises:
        ValueError: if no condition is given.
        TypeError: if a condition is neither a ``BaseCondition`` nor
            callable.

    Example:
        ```pycon
        >>> from minevent import OrCondition, OnceCondition, PeriodicCondition
        >>> condition = OrCondition(OnceCondition(), PeriodicCondition(3))
        >>> [condition.evaluate() for _ in range(4)]
        [True, False, False, True]

        ```
    """

    def evaluate(self) -> bool:
        results = [condition.evaluate() for condition in self._conditions]
        return any(results)


class NotCondition(BaseCondition):
    r"""Implement a condition that negates another condition.

    Args:
        condition: The condition to negate. A function without
            argument that returns a boolean is accepted.

    Raises:
        TypeError: if ``condition`` is neither a ``BaseCondition``
            nor callable.

    Example:
        ```pycon
        >>> from minevent import NotCondition, OnceCondition
        >>> condition = NotCondition(OnceCondition())
        >>> condition.evaluate()
        False
        >>> condition.evaluate()
        True

        ```
    """

    def __init__(self, condition: BaseCondition | Callable[[], bool]) -> None:
        self._condition = as_condition(condition)

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self._condition!r})"

    @property
    def condition(self) -> BaseCondition:
        r"""Get the negated condition.

        Returns:
            The condition.
        """
        return self._condition

    def equal(self, other: object) -> bool:
        if isinstance(other, NotCondition):
            return objects_are_equal(self._condition, other.condition)
        return False

    def evaluate(self) -> bool:
        return not self._condition.evaluate()
