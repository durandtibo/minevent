r"""Implement how the code of a user is called.

``Handler`` is the type of a handler. ``check_signature`` rejects a
handler or a condition that cannot be called with the context,
``has_kind`` says if it is a generator or a coroutine function,
``describe`` names it, ``describe_event`` shows an event name,
``reject_awaitable`` rejects the awaitable result of a synchronous call,
and ``add_error_note`` completes the exception that it raises. These
helpers are used by ``minevent.manager``, and ``minevent`` exports
``Handler`` only.
"""

from __future__ import annotations

__all__ = [
    "Handler",
    "add_error_note",
    "check_signature",
    "describe",
    "describe_event",
    "has_kind",
    "reject_awaitable",
]

import contextlib
import functools
import inspect
import reprlib
import sys
from collections.abc import Awaitable, Callable, Coroutine

from minevent.context import Context

if sys.version_info >= (3, 14):
    import annotationlib

# The event name in a message or a note. The default limits of ``reprlib`` (30 characters) would
# cut ordinary names, such as the ``repr`` of a ``StrEnum`` member, which ``maxother`` limits.
_EVENT_REPR = reprlib.Repr()
_EVENT_REPR.maxstring = _EVENT_REPR.maxother = 200

Handler = Callable[[Context], object]
"""A handler: a function of the ``Context`` of the trigger."""


def check_signature(func: Callable[..., object], name: str) -> None:
    r"""Check that a handler or a condition can be called with the
    context.

    A handler and a condition are always called as ``func(context)``.
    Exactly one parameter must lack a default, and it must be
    positional: it receives the context. The other parameters keep their
    default, because the manager never fills them. Names and annotations
    are not checked. Any other signature is rejected, including
    ``*args`` and ``**kwargs`` (they do not say whether the context is
    expected), and so is a callable whose signature cannot be inspected.
    A generator function or an async generator function, and a callable
    object whose ``__call__`` is one (see ``has_kind``), is rejected too,
    because calling it runs none of its code. The signature is the one
    that ``inspect.signature`` reports: it does not contain the
    positional arguments that a ``functools.partial`` binds, and it is
    the one of the wrapped function for a decorator that uses
    ``functools.wraps``. The annotations do not have to be resolvable:
    on Python 3.14+, a name that is only imported under
    ``TYPE_CHECKING`` is kept as a forward reference instead of raising
    a ``NameError``. ``func`` is not called.

    Args:
        func: The callable to inspect.
        name: The name of the argument that receives ``func``, used in
            the error messages.

    Raises:
        TypeError: if ``func`` is a generator function or an async
            generator function (see ``has_kind``), if its signature
            cannot be inspected, or if it cannot be called with the
            context as its only argument.

    Example:
        ```pycon
        >>> from minevent.calls import check_signature
        >>> def read_epoch(context):
        ...     return context["epoch"]
        ...
        >>> check_signature(read_epoch, "handler")
        >>> def train(mode=True): ...
        ...
        >>> check_signature(train, "handler")
        Traceback (most recent call last):
        ...
        TypeError: handler train must take the context as its only required argument; wrap it in a function or a lambda

        ```
    """
    if has_kind(func, inspect.isgeneratorfunction) or has_kind(func, inspect.isasyncgenfunction):
        msg = f"{name} must not be a generator function, but got {describe(func)}"
        raise TypeError(msg)
    msg = (
        f"{name} {describe(func)} must take the context as its only required argument; "
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
    # The parameters that have a default keep it. A ``*args`` or a ``**kwargs`` parameter has no
    # default.
    required = [param for param in signature.parameters.values() if param.default is param.empty]
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(required) != 1 or required[0].kind not in positional:
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


def describe_event(event: str) -> str:
    r"""Show an event name in a message of the package.

    A name is shown by its ``repr``, shortened in the middle above 200
    characters, so the size of a message does not depend on the size of
    the name.

    Args:
        event: The event name.

    Returns:
        The ``repr`` of ``event``, of at most 200 characters. If the
            ``repr`` of a subclass of ``str`` raises an ``Exception``, a
            placeholder of ``reprlib`` that names its class is returned.

    Example:
        ```pycon
        >>> from minevent.calls import describe_event
        >>> describe_event("epoch_end")
        "'epoch_end'"
        >>> len(describe_event("x" * 1000))
        200

        ```
    """
    return _EVENT_REPR.repr(event)


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
        event: The event that was triggered (see ``describe_event``).

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
        note = f"raised by {source} while handling the event {describe_event(event)}"
        if note not in getattr(exc, "__notes__", ()):
            exc.add_note(note)
