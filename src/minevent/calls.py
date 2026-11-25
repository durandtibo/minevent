r"""Implement how the code of a user is called.

``needs_context`` says how a handler or a condition is called,
``describe`` names it, ``reject_awaitable`` rejects the awaitable result
of a synchronous call, and ``add_error_note`` completes the exception
that it raises. These helpers are used by ``minevent.manager``, and
``minevent`` does not export them.
"""

from __future__ import annotations

__all__ = ["add_error_note", "describe", "needs_context", "reject_awaitable"]

import functools
import sys
from collections.abc import Awaitable, Coroutine
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def needs_context(func: Callable[..., object], name: str) -> bool:
    r"""Indicate if a handler or a condition must be called with the
    context.

    A callable is called as ``func()`` or ``func(context)``. A
    parameter that has a default keeps it: the manager never fills it.
    The callable is called as ``func()`` if no other parameter is left,
    and as ``func(context)`` if exactly one is left and it is positional.
    Names and annotations are not checked. Any other signature is
    rejected, including ``*args`` and ``**kwargs`` (they do not say
    whether the context is expected), and so is a callable whose
    signature cannot be inspected. A generator function or an async
    generator function is rejected too, because calling it runs none of
    its code. The signature is the one that ``inspect.signature``
    reports: it does not contain the positional arguments that a
    ``functools.partial`` binds, and it is the one of the wrapped
    function for a decorator that uses ``functools.wraps``. The
    annotations do not have to be resolvable: on Python 3.14+, a name
    that is only imported under ``TYPE_CHECKING`` is kept as a forward
    reference instead of raising a ``NameError``.

    Args:
        func: The callable to inspect.
        name: The name of the argument that receives ``func``, used in
            the error messages.

    Returns:
        ``True`` if ``func`` is called as ``func(context)``, and
            ``False`` if it is called as ``func()``.

    Raises:
        TypeError: if ``func`` is a generator function, if its
            signature cannot be inspected, or if it needs another
            argument than the context.

    Example:
        ```pycon
        >>> from minevent.calls import needs_context
        >>> def func(): ...
        >>> needs_context(func, "handler")
        False
        >>> def func(context): ...
        >>> needs_context(func, "handler")
        True
        >>> def func(mode=True): ...
        >>> needs_context(func, "handler")
        False

        ```
    """
    import inspect  # noqa: PLC0415

    if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
        msg = f"{name} must not be a generator function, but got {describe(func)}"
        raise TypeError(msg)
    msg = (
        f"{name} {describe(func)} must need no argument or only the context; "
        "wrap it in a function or a lambda"
    )
    try:
        if sys.version_info >= (3, 14):
            # The annotations are evaluated lazily, and an unresolved name must not raise.
            import annotationlib  # noqa: PLC0415

            signature = inspect.signature(func, annotation_format=annotationlib.Format.FORWARDREF)
        else:
            signature = inspect.signature(func)
    except (TypeError, ValueError) as exc:
        raise TypeError(msg) from exc
    # The parameters that have a default keep it: only the others need a value. A ``*args`` or a
    # ``**kwargs`` parameter has no default.
    required = [param for param in signature.parameters.values() if param.default is param.empty]
    if not required:
        return False
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(required) == 1 and required[0].kind in positional:
        return True
    raise TypeError(msg)


def describe(func: Callable[..., object]) -> str:
    r"""Name a handler or a condition without calling the ``repr`` of its
    data.

    The ``repr`` of a callable can contain its arguments, which can be
    large or raise, so it is not used in the messages of the package.

    Args:
        func: The callable to name.

    Returns:
        The qualified name of the function under a
            ``functools.partial`` (nested partials are unwrapped), or
            the qualified name of the class of the callable if it has
            no name (for example a callable object).

    Example:
        ```pycon
        >>> import functools
        >>> from minevent.calls import describe
        >>> describe(print)
        'print'
        >>> describe(functools.partial(print, "Hello!"))
        'print'

        ```
    """
    while isinstance(func, functools.partial):
        func = func.func
    return getattr(func, "__qualname__", type(func).__qualname__)


def reject_awaitable(result: object, message: str) -> None:
    r"""Reject the value returned by a function that must be synchronous.

    A coroutine is closed, so it does not emit a ``RuntimeWarning``
    because it was never awaited. Another awaitable, such as a future,
    is not modified.

    Args:
        result: The value returned by a handler or a condition.
        message: The message of the error. It names the function that
            returned ``result``.

    Raises:
        TypeError: if ``result`` is an awaitable.

    Example:
        ```pycon
        >>> from minevent.calls import reject_awaitable
        >>> reject_awaitable(True, "the function returned an awaitable")

        ```
    """
    if isinstance(result, Awaitable):
        if isinstance(result, Coroutine):
            result.close()
        raise TypeError(message)


def add_error_note(exc: Exception, event: str, handler: Callable[..., object]) -> None:
    r"""Add a note to the exception raised by an event handler.

    The note names the event and the function of the handler, never
    its arguments. The note is not added if the exception already has
    it, so an exception instance that is raised again (or a handler
    that triggers its own event) has one note per distinct pair of
    event and handler.

    Args:
        exc: The exception raised by the event handler.
        event: The event that was triggered.
        handler: The handler that raised the exception.

    Example:
        ```pycon
        >>> from minevent.calls import add_error_note
        >>> error = ValueError("boom")
        >>> add_error_note(error, "my_event", print)
        >>> error.__notes__
        ["raised by print while handling the event 'my_event'"]

        ```
    """
    note = f"raised by {describe(handler)} while handling the event {event!r}"
    if note not in getattr(exc, "__notes__", ()):
        exc.add_note(note)
