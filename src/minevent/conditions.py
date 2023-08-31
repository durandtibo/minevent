r"""This module defines some conditions that can be used in the event
system."""

from __future__ import annotations

__all__ = ["BaseCondition", "PeriodicCondition"]

from abc import ABC, abstractmethod
from typing import Any


class BaseCondition(ABC):
    r"""Defines the base class to implement a condition for
    ``ConditionalEventHandler``.

    A child class has to implement the following methods:

        - ``evaluate``
        - ``equal``

    Example usage:

    .. code-block:: pycon

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
    """

    def __eq__(self, other: Any) -> bool:
        return self.equal(other)

    @abstractmethod
    def equal(self, other: Any) -> bool:
        r"""Compares two conditions.

        Args:
        ----
            other: Specifies the other object to compare with.

        Returns:
        -------
            bool: ``True`` if the two conditions are equal,
                otherwise ``False``.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import PeriodicCondition
            >>> condition = PeriodicCondition(freq=3)
            >>> condition.equal(PeriodicCondition(freq=3))
            True
            >>> condition.equal(PeriodicCondition(freq=2))
            False
        """

    @abstractmethod
    def evaluate(self) -> bool:
        r"""Evaluates the condition given the current state.

        Returns
        -------
            bool: ``True`` if the condition is ``True`` and the event
                handler logic should be executed, otherwise ``False``.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> handler = EventHandler(hello_handler)
            >>> handler.handle()
            Hello!
        """


class PeriodicCondition(BaseCondition):
    r"""Implements a periodic condition.

    This condition is true every ``freq`` events.

    Args:
    ----
        freq (int): Specifies the frequency.

    Example usage:

    .. code-block:: pycon

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
    """

    def __init__(self, freq: int) -> None:
        self._freq = int(freq)
        self._step = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(freq={self._freq:,}, step={self._step:,})"

    @property
    def freq(self) -> int:
        r"""``int``: The frequency of the condition."""
        return self._freq

    def equal(self, other: Any) -> bool:
        if isinstance(other, PeriodicCondition):
            return self.freq == other.freq
        return False

    def evaluate(self) -> bool:
        condition = self._step % self._freq == 0
        self._step += 1
        return condition
