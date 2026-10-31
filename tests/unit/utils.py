from __future__ import annotations

__all__ = ["trace"]

from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def trace(func: Callable) -> Callable:
    r"""Wrap a function to record how it is called.

    The returned wrapper exposes the ``called``, ``call_count``,
    ``args`` and ``kwargs`` attributes, which describe the calls made.

    Args:
        func: The function to wrap.

    Returns:
        The wrapped function.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        wrapper.called = True
        wrapper.call_count += 1
        wrapper.args = args
        wrapper.kwargs = kwargs
        return func(*args, **kwargs)

    wrapper.called = False
    wrapper.call_count = 0
    wrapper.args = ()
    wrapper.kwargs = {}
    return wrapper
