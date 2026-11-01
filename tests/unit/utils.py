from __future__ import annotations

__all__ = ["Tracer", "trace"]

from functools import update_wrapper
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class Tracer:
    r"""Wrap a function to record how it is called.

    The tracer exposes the ``called``, ``call_count``, ``args`` and
    ``kwargs`` attributes, which describe the calls made.

    Args:
        func: The function to wrap.
    """

    def __init__(self, func: Callable[..., Any]) -> None:
        self._func = func
        update_wrapper(self, func)
        self.reset()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.called = True
        self.call_count += 1
        self.args = args
        self.kwargs = kwargs
        return self._func(*args, **kwargs)

    def reset(self) -> None:
        r"""Forget the calls made so far."""
        self.called = False
        self.call_count = 0
        self.args: tuple[Any, ...] = ()
        self.kwargs: dict[str, Any] = {}


def trace(func: Callable[..., Any]) -> Tracer:
    r"""Wrap a function to record how it is called.

    Args:
        func: The function to wrap.

    Returns:
        The ``Tracer`` that wraps the function.
    """
    return Tracer(func)
