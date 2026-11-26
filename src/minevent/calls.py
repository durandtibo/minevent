r"""Implement how the code of a user is called.

``Handler`` is the type of a handler. ``adapt_call`` turns a handler or
a condition into a callable of the context, ``has_kind`` says if it is a
generator or a coroutine function, ``describe`` names it,
``reject_awaitable`` rejects the awaitable result of a synchronous call,
and ``add_error_note`` completes the exception that it raises. These
helpers are used by ``minevent.manager``, and ``minevent`` exports
``Handler`` only.
"""

from __future__ import annotations

__all__ = [
    "Handler",
    "adapt_call",
    "add_error_note",
    "describe",
    "has_kind",
    "reject_awaitable",
]

import contextlib
import functools
import inspect
import sys
from collections.abc import Awaitable, Callable, Coroutine

from minevent.context import Context

if sys.version_info >= (3, 14):
    import annotationlib

Handler = Callable[[], object] | Callable[[Context], object]
"""A handler: a function without parameter or with the ``Context`` of
the trigger."""


def adapt_call(func: Callable[..., object], name: str) -> Callable[[Context], object]:
    r"""Turn a handler or a condition into a callable of the context.

    A callable is called as ``func()`` or ``func(context)``. A
    parameter that has a default keeps it: the manager never fills it.
    The callable is called as ``func()`` if no other parameter is left,
    and as ``func(context)`` if exactly one is left and it is positional.
    Names and annotations are not checked. Any other signature is
    rejected, including ``*args`` and ``**kwargs`` (they do not say
    whether the context is expected), and so is a callable whose
    signature cannot be inspected. A generator function or an async
    generator function, and a callable object whose ``__call__`` is one
    (see ``has_kind``), is rejected too, because calling it runs none of
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
        ``func`` itself if it is called as ``func(context)``, and
            otherwise a function of the context that calls ``func()``.
            The signature is read once, by this function: calling the
            result does not read it again.

    Raises:
        TypeError: if ``func`` is a generator function or an async
            generator function (see ``has_kind``), if its
            signature cannot be inspected, or if it needs another
            argument than the context.

    Example:
        ```pycon
        >>> from minevent import Context
        >>> from minevent.calls import adapt_call
        >>> def read_epoch(context):
        ...     return context["epoch"]
        ...
        >>> adapt_call(read_epoch, "handler") is read_epoch
        True
        >>> def train(mode=True):
        ...     return mode
        ...
        >>> adapt_call(train, "handler")(Context({"epoch": 3}))
        True

        ```
    """
    if has_kind(func, inspect.isgeneratorfunction) or has_kind(func, inspect.isasyncgenfunction):
        msg = f"{name} must not be a generator function, but got {describe(func)}"
        raise TypeError(msg)
    msg = (
        f"{name} {describe(func)} must need no argument or only the context; "
        "wrap it in a function or a lambda"
    )
    try:
        if sys.version_info >= (3, 14):
            # The annotations are evaluated lazily, and an unresolved name must not raise.
            signature = inspect.signature(func, annotation_format=annotationlib.Format.FORWARDREF)
        else:
            signature = inspect.signature(func)
    except (TypeError, ValueError) as exc:
        raise TypeError(msg) from exc
    # The parameters that have a default keep it: only the others need a value. A ``*args`` or a
    # ``**kwargs`` parameter has no default.
    required = [param for param in signature.parameters.values() if param.default is param.empty]
    if not required:
        return lambda _context: func()
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(required) == 1 and required[0].kind in positional:
        return func
    raise TypeError(msg)


def has_kind(func: Callable[..., object], predicate: Callable[[object], bool]) -> bool:
    r"""Indicate if the code that a call runs is of a given kind.

    A ``functools.partial`` is judged by its function (nested partials
    are unwrapped). A callable object is judged by its ``__call__``,
    unless the predicate already accepts the object itself, for example
    one marked with ``inspect.markcoroutinefunction``. A class is not
    judged by the ``__call__`` of its instances: calling it creates one.

    Args:
        func: The callable to inspect.
        predicate: A function of ``inspect`` that recognizes a kind of
            function, such as ``inspect.iscoroutinefunction`` or
            ``inspect.isgeneratorfunction``.

    Returns:
        ``True`` if ``predicate`` accepts the function or the
            ``__call__`` that a call of ``func`` runs.

    Example:
        ```pycon
        >>> import inspect
        >>> from minevent.calls import has_kind
        >>> class Notifier:
        ...     async def __call__(self):
        ...         pass
        ...
        >>> has_kind(Notifier(), inspect.iscoroutinefunction)
        True
        >>> has_kind(Notifier, inspect.iscoroutinefunction)
        False

        ```
    """
    while isinstance(func, functools.partial):
        func = func.func
    if predicate(func):
        return True
    # A function or a method has no other code than its own: only an object has a ``__call__``.
    return not inspect.isroutine(func) and predicate(type(func).__call__)


def describe(func: object) -> str:
    r"""Name a handler or a condition without calling the ``repr`` of its
    data.

    The ``repr`` of a callable can contain its arguments, which can be
    large or raise, so it is not used in the messages of the package.
    Naming never raises an ``Exception``, so it cannot replace the error
    that the name is used to report.

    Args:
        func: The object to name, usually a handler or a condition.

    Returns:
        The qualified name of the function under a
            ``functools.partial`` (nested partials are unwrapped), or
            the qualified name of the class of the object if it has no
            name (for example a callable object), if its name is not a
            ``str``, or if reading its name raises.

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
    # A proxy can raise any exception when one of its attributes, ``__class__`` included, is read.
    with contextlib.suppress(Exception):
        while isinstance(func, functools.partial):
            func = func.func
        name = getattr(func, "__qualname__", None)
        if isinstance(name, str):
            return name
    return type(func).__qualname__


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


def add_error_note(exc: Exception, source: str, event: str) -> None:
    r"""Add a note to the exception raised while handling an event.

    The note says what raised and while handling which event. It is not
    added if the exception already has it, so an exception instance that
    is raised again (or a handler that triggers its own event) has one
    note per distinct note. Adding the note never replaces the
    exception: if the note cannot be added, for example to a
    ``frozen=True`` dataclass exception, the exception is left without
    it.

    Args:
        exc: The exception raised by a handler or a condition.
        source: What raised the exception, for example the name of the
            handler (see ``describe``).
        event: The event that was triggered.

    Example:
        ```pycon
        >>> from minevent.calls import add_error_note
        >>> error = ValueError("boom")
        >>> add_error_note(error, "log_epoch", "epoch_end")
        >>> error.__notes__
        ["raised by log_epoch while handling the event 'epoch_end'"]

        ```
    """
    # A frozen exception, or one with unusual ``__notes__``, cannot take the note.
    with contextlib.suppress(Exception):
        note = f"raised by {source} while handling the event {event!r}"
        if note not in getattr(exc, "__notes__", ()):
            exc.add_note(note)
