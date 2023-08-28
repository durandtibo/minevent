r"""This module defines some conditions that can be used in the event
system."""

from __future__ import annotations

__all__ = ["PeriodicCondition"]

from typing import Any


class PeriodicCondition:
    r"""Implements a periodic condition.

    This condition is true every ``freq`` events.

    Args:
    ----
        freq (int): Specifies the frequency.

    Example usage:

    .. code-block:: pycon

        >>> from minevent import PeriodicCondition
        >>> condition = PeriodicCondition(freq=3)
        >>> condition()
        True
        >>> condition()
        False
        >>> condition()
        False
        >>> condition()
        True
        >>> condition()
        False
        >>> condition()
        False
        >>> condition()
        True
    """

    def __init__(self, freq: int) -> None:
        self._freq = int(freq)
        self._step = 0

    def __call__(self) -> bool:
        r"""Evaluates the condition given the current state.

        Returns
        -------
            bool: ``True`` if the condition is ``True``, otherwise
                ``False``.
        """
        condition = self._step % self._freq == 0
        self._step += 1
        return condition

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PeriodicCondition):
            return self.freq == other.freq
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(freq={self._freq:,}, step={self._step:,})"

    @property
    def freq(self) -> int:
        r"""``int``: The frequency of the condition."""
        return self._freq
