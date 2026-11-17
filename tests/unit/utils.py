from __future__ import annotations

__all__ = ["Tracer", "raised", "reset_traced", "trace"]

from functools import update_wrapper
from typing import TYPE_CHECKING, Any

import pytest

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
        self.__wrapped__ = func
        update_wrapper(self, func)
        self.reset()

    def __call__(self, /, *args: Any, **kwargs: Any) -> Any:
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


_TRACED: list[Tracer] = []


def trace(func: Callable[..., Any]) -> Tracer:
    r"""Wrap a function to record how it is called.

    The tracer is registered, so ``reset_traced`` resets it. This is
    meant for the module-level handlers shared by the tests of a
    module.

    Args:
        func: The function to wrap.

    Returns:
        The ``Tracer`` that wraps the function.
    """
    tracer = Tracer(func)
    _TRACED.append(tracer)
    return tracer


def reset_traced() -> None:
    r"""Reset all the tracers created with ``trace``."""
    for tracer in _TRACED:
        tracer.reset()


def raised(func: Callable[..., object], *args: object, **kwargs: object) -> BaseException:
    r"""Return the exception raised by a call, and fail if it does not
    raise.

    Args:
        func: The function to call.
        *args: The positional arguments of the call.
        **kwargs: The keyword arguments of the call.

    Returns:
        The exception raised by ``func(*args, **kwargs)``.
    """
    with pytest.raises(BaseException, match=r"(?s).*") as exc_info:
        func(*args, **kwargs)
    return exc_info.value
