r"""Implement some conditions that can be used in the event system."""

from __future__ import annotations

__all__ = ["BaseCondition", "PeriodicCondition"]

from abc import ABC, abstractmethod
from typing import Any


class BaseCondition(ABC):  # noqa: PLW1641
    r"""Define the base class to implement a condition for
    ``ConditionalEventHandler``.

    A child class has to implement the following methods:

        - ``evaluate``
        - ``equal``

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
    def equal(self, other: Any) -> bool:
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
            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> handler = EventHandler(hello_handler)
            >>> handler.handle()
            Hello!

            ```
        """


class PeriodicCondition(BaseCondition):
    r"""Implement a periodic condition.

    This condition evaluates to ``True`` every ``freq`` calls to the
    ``evaluate`` method. It maintains an internal counter that
    increments with each evaluation. The condition is ``True`` when
    the counter modulo ``freq`` equals zero.

    Args:
        freq: The frequency (interval) at which the condition
            evaluates to ``True``. Must be a positive integer.

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

    def __init__(self, freq: int) -> None:
        self._freq = int(freq)
        self._step = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(freq={self._freq:,}, step={self._step:,})"

    @property
    def freq(self) -> int:
        r"""Get the frequency of the periodic condition.

        Returns:
            The number of evaluations between each ``True`` result.
                The condition evaluates to ``True`` every ``freq``
                calls.
        """
        return self._freq

    def equal(self, other: Any) -> bool:
        if isinstance(other, PeriodicCondition):
            return self.freq == other.freq
        return False

    def evaluate(self) -> bool:
        condition = self._step % self._freq == 0
        self._step += 1
        return condition
