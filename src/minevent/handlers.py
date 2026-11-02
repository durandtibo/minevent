r"""Implement the event handlers."""

from __future__ import annotations

__all__ = ["BaseEventHandler", "EventHandler"]

import inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from minevent.conditions import Condition


class BaseEventHandler(ABC):
    r"""Define the base class to implement an event handler.

    A child class has to implement the ``handle`` method. Event
    handlers are compared by identity, so they can be put in a ``set``
    or used as ``dict`` keys. Use the ``Subscription`` returned by
    ``EventManager.add_event_handler`` to identify a registration.

    Example:
        ```pycon
        >>> from minevent import EventHandler
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> handler = EventHandler(hello_handler)
        >>> handler
        EventHandler(handler=<function hello_handler at 0x...>, handler_args=(), handler_kwargs={}, condition=None, filter_payload=False)
        >>> handler.handle()
        Hello!

        ```
    """

    @abstractmethod
    def handle(self, /, **payload: object) -> None:
        r"""Handle the event.

        This method executes the logic associated with the event
        handler. It should be implemented by child classes to define
        the specific behavior when an event is triggered.

        Args:
            **payload: The keyword arguments given to
                ``EventManager.trigger_event``. The payload is empty
                when the event is triggered without data.

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

    async def ahandle(self, /, **payload: object) -> None:
        r"""Handle the event asynchronously.

        This method is called by ``EventManager.atrigger_event``. The
        default implementation calls ``handle``, so it works for
        synchronous event handlers. Child classes that support
        coroutines should override it.

        Args:
            **payload: The keyword arguments given to
                ``EventManager.atrigger_event``.

        Example:
            ```pycon
            >>> import asyncio
            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> asyncio.run(EventHandler(hello_handler).ahandle())
            Hello!

            ```
        """
        self.handle(**payload)


def _accepted_keywords(func: Callable[..., object]) -> frozenset[str] | None:
    r"""Get the keyword arguments that a callable accepts.

    Args:
        func: The callable to inspect.

    Returns:
        The names of the parameters that can be passed by keyword,
            or ``None`` if the callable accepts any keyword (it has a
            ``**kwargs`` parameter) or if its signature cannot be
            inspected.

    Example:
        ```pycon
        >>> from minevent.handlers import _accepted_keywords
        >>> def func(a, /, b, *, c, **kwargs): ...
        >>> _accepted_keywords(func) is None
        True
        >>> def func(a, /, b, *, c): ...
        >>> sorted(_accepted_keywords(func))
        ['b', 'c']

        ```
    """
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters):
        return None
    return frozenset(
        param.name
        for param in parameters
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    )


class EventHandler(BaseEventHandler):
    r"""Implement an event handler.

    This class wraps a callable function or method and allows it to be
    executed as an event handler. The handler can be configured with
    positional and keyword arguments that will be passed when the
    handler is executed, and with an optional condition. When a
    condition is given, the handler is executed only if the condition
    evaluates to ``True``. This is useful for scenarios where event
    handlers should only run under specific circumstances, such as
    periodic execution or state-based triggering.

    The handler is called as
    ``handler(*handler_args, **handler_kwargs, **payload)``, where
    ``payload`` is the data given when the event is triggered.

    Args:
        handler: The callable function or method to be invoked when
            the event is triggered (and the condition is ``True``).
        handler_args: The positional arguments to pass to the handler
            when it is called. Default is ``None``.
        handler_kwargs: The keyword arguments to pass to the handler
            when it is called. The dictionary is copied, so changing
            it afterwards does not change the handler.
            Default is ``None``.
        condition: The condition that controls whether the handler
            is executed: a function without argument that returns a
            boolean, such as a lambda or a ``PeriodicCondition``. It
            is called each time the event is triggered, before the
            handler. If ``None``, the handler is always executed.
            Default is ``None``.
        filter_payload: If ``True``, only the payload keys that the
            signature of the handler accepts are passed to it, so
            handlers with different needs can share an event without
            ``**kwargs``. The accepted keys are computed once, at
            construction. A handler with a ``**kwargs`` parameter, or
            whose signature cannot be inspected, receives the whole
            payload. Keys of ``handler_kwargs`` are not filtered.
            Default is ``False``.

    Raises:
        TypeError: if ``handler`` is not callable, if
            ``handler_args`` is a ``str`` or ``bytes`` (which would
            be split into characters), or if ``condition`` is
            neither ``None`` nor callable.

    Example:
        ```pycon
        >>> from minevent import EventHandler, PeriodicCondition
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> handler = EventHandler(hello_handler)
        >>> handler
        EventHandler(handler=<function hello_handler at 0x...>, handler_args=(), handler_kwargs={}, condition=None, filter_payload=False)
        >>> handler.handle()
        Hello!
        >>> handler = EventHandler(print, handler_args=["Hello!"])
        >>> handler.handle()
        Hello!
        >>> handler = EventHandler(hello_handler, condition=PeriodicCondition(freq=3))
        >>> handler
        EventHandler(handler=<function hello_handler at 0x...>, handler_args=(), handler_kwargs={}, condition=PeriodicCondition(freq=3, skip_first=False, step=0), filter_payload=False)
        >>> handler.handle()
        Hello!
        >>> handler.handle()
        >>> handler.handle()
        >>> handler.handle()
        Hello!
        >>> def epoch_handler(epoch: int) -> None:
        ...     print(f"epoch {epoch}")
        ...
        >>> handler = EventHandler(epoch_handler, filter_payload=True)
        >>> handler.handle(epoch=3, loss=0.5)
        epoch 3

        ```
    """

    def __init__(
        self,
        handler: Callable[..., object],
        handler_args: Sequence[Any] | None = None,
        handler_kwargs: Mapping[str, Any] | None = None,
        *,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> None:
        if not callable(handler):
            msg = f"handler is not callable: {handler}"
            raise TypeError(msg)
        if isinstance(handler_args, (str, bytes)):
            msg = f"handler_args must be a sequence of arguments, not a string: {handler_args!r}"
            raise TypeError(msg)
        if condition is not None and not callable(condition):
            msg = f"condition is not callable: {condition}"
            raise TypeError(msg)
        self._handler = handler
        self._handler_args = () if handler_args is None else tuple(handler_args)
        self._handler_kwargs = {} if handler_kwargs is None else dict(handler_kwargs)
        self._condition = condition
        self._filter_payload = filter_payload
        self._payload_keys = _accepted_keywords(handler) if filter_payload else None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}(handler={self._handler!r}, "
            f"handler_args={self._handler_args!r}, handler_kwargs={self._handler_kwargs!r}, "
            f"condition={self._condition!r}, filter_payload={self._filter_payload})"
        )

    @property
    def handler(self) -> Callable[..., object]:
        r"""Get the handler function.

        Returns:
            The handler function that will be called when the event
                is triggered.
        """
        return self._handler

    @property
    def handler_args(self) -> tuple[Any, ...]:
        r"""Get the positional arguments for the handler.

        Returns:
            A tuple containing the positional arguments that will be
                passed to the handler when it is called.
        """
        return self._handler_args

    @property
    def handler_kwargs(self) -> dict[str, Any]:
        r"""Get the keyword arguments for the handler.

        Returns:
            A copy of the dictionary containing the keyword arguments
                that will be passed to the handler when it is called.
                Modifying the returned dictionary does not change the
                handler.
        """
        return dict(self._handler_kwargs)

    @property
    def condition(self) -> Condition | None:
        r"""Get the condition that controls handler execution.

        Returns:
            The condition that must evaluate to ``True`` for the
                handler to be executed, or ``None`` if the handler is
                always executed.
        """
        return self._condition

    @property
    def filter_payload(self) -> bool:
        r"""Indicate if the payload is filtered by the signature of the
        handler.

        Returns:
            ``True`` if only the payload keys accepted by the handler
                are passed to it, otherwise ``False``.
        """
        return self._filter_payload

    def _select_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        r"""Select the payload keys to pass to the handler.

        Args:
            payload: The payload given to ``handle``.

        Returns:
            The payload if it is not filtered or if the handler
                accepts any keyword, otherwise the items of the
                payload whose key is accepted by the handler.
        """
        if self._payload_keys is None:
            return payload
        return {key: value for key, value in payload.items() if key in self._payload_keys}

    def _call(self, payload: dict[str, Any]) -> object:
        r"""Call the handler if the condition is ``True``.

        Args:
            payload: The payload given to ``handle`` or ``ahandle``.

        Returns:
            The value returned by the handler, or ``None`` if the
                condition is ``False``.
        """
        if self._condition is not None and not self._condition():
            return None
        return self._handler(
            *self._handler_args, **self._handler_kwargs, **self._select_payload(payload)
        )

    def handle(self, /, **payload: object) -> None:
        r"""Handle the event.

        Calls the handler if the condition is ``True`` (or if there is
        no condition). The handler must be synchronous: a coroutine
        function would be silently dropped, so it is rejected.

        Args:
            **payload: The keyword arguments given to
                ``EventManager.trigger_event``. The payload is empty
                when the event is triggered without data.

        Raises:
            TypeError: if the handler returns an awaitable. Use
                ``ahandle`` (or ``EventManager.atrigger_event``) with
                coroutine functions.

        Example:
            ```pycon
            >>> from minevent import EventHandler
            >>> async def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> EventHandler(hello_handler).handle()
            Traceback (most recent call last):
                ...
            TypeError: ...hello_handler... returned an awaitable; use ahandle or atrigger_event

            ```
        """
        result = self._call(payload)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            msg = f"{self._handler!r} returned an awaitable; use ahandle or atrigger_event"
            raise TypeError(msg)

    async def ahandle(self, /, **payload: object) -> None:
        r"""Handle the event asynchronously.

        Like ``handle``, but if the handler returns an awaitable (for
        example because it is a coroutine function), the awaitable is
        awaited. ``handle`` raises a ``TypeError`` for an awaitable, so
        use ``ahandle`` (or ``EventManager.atrigger_event``) with
        coroutine functions.

        Args:
            **payload: The keyword arguments given to
                ``EventManager.atrigger_event``.

        Example:
            ```pycon
            >>> import asyncio
            >>> from minevent import EventHandler
            >>> async def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> asyncio.run(EventHandler(hello_handler).ahandle())
            Hello!

            ```
        """
        result = self._call(payload)
        if inspect.isawaitable(result):
            await result
