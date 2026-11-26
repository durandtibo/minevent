r"""Implement the event manager and the subscriptions.

``EventManager`` stores the registrations of the handlers and triggers
the events, and ``Subscription`` is the registration of one handler to
one event. The conditions of a registration are in
``minevent.conditions``.
"""

from __future__ import annotations

__all__ = ["EventManager", "Subscription"]

import inspect
import reprlib
import threading
from collections.abc import Awaitable, Mapping
from typing import TYPE_CHECKING, NoReturn, Self, TypeVar

from minevent.calls import (
    Handler,
    adapt_call,
    add_error_note,
    describe,
    describe_event,
    has_kind,
    reject_awaitable,
)
from minevent.context import Context

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from minevent.conditions import Condition

_F = TypeVar("_F", bound=Handler)


def _check_event(event: object) -> None:
    r"""Check that an event name is a string.

    Args:
        event: The event name to check.

    Raises:
        TypeError: if ``event`` is not a ``str``.

    Example:
        ```pycon
        >>> from minevent.manager import _check_event
        >>> _check_event("epoch_end")

        ```
    """
    if not isinstance(event, str):
        msg = f"event must be a str, but got {type(event).__qualname__}"
        raise TypeError(msg)


_EMPTY_CONTEXT = Context()


def _as_context(context: object) -> Context:
    r"""Convert the data of a trigger to a context.

    Args:
        context: The data given to ``trigger_event`` or
            ``atrigger_event``: a mapping from ``str`` to values, a
            ``Context``, or ``None``.

    Returns:
        ``context`` itself if it is a ``Context`` (it is immutable, so
            it is shared, not copied), a shared empty context if it is
            ``None``, and a new ``Context`` that copies the mapping
            otherwise.

    Raises:
        TypeError: if ``context`` is neither ``None`` nor a mapping, or
            if a key of the mapping is not a ``str``.

    Example:
        ```pycon
        >>> from minevent.manager import _as_context
        >>> _as_context({"epoch": 3})
        Context({'epoch': 3})
        >>> _as_context(None)
        Context({})

        ```
    """
    if context is None:
        return _EMPTY_CONTEXT
    if isinstance(context, Context):
        return context
    if not isinstance(context, Mapping):
        msg = f"context must be a mapping or None, but got {type(context).__qualname__}"
        raise TypeError(msg)
    return Context(context)


class Subscription:
    r"""Represent the registration of a handler to an event.

    ``EventManager.add_event_handler`` returns a subscription: it is the
    registration itself, so ``remove`` removes that registration only,
    even if the same handler is registered several times. Subscriptions
    are compared by identity, and copying or pickling one raises a
    ``TypeError``. A subscription is a context manager: the
    registration is removed when the ``with`` block exits.

    The constructor is internal: subscriptions are created by the event
    manager, and one that is built by hand is not ``active``.

    Args:
        manager: The event manager that stores the registration.
        event: The event name of the registration.
        handler: The registered handler (``Handler``).
        once: If ``True``, the handler runs at most once. Default is
            ``False``.
        condition: The condition evaluated before the handler, or
            ``None`` if the handler always runs. Default is ``None``.

    Raises:
        TypeError: if ``EventManager.add_event_handler`` rejects
            ``handler`` or ``condition``.

    Example:
        ```pycon
        >>> from minevent import EventManager
        >>> manager = EventManager()
        >>> subscription = manager.add_event_handler("my_event", lambda: None)
        >>> subscription
        Subscription(event='my_event', handler='<lambda>')
        >>> subscription.remove(), subscription.remove()
        (True, False)
        >>> subscription.active
        False
        >>> with manager.add_event_handler("my_event", lambda: None):
        ...     len(manager)
        ...
        1
        >>> len(manager)
        0

        ```
    """

    def __init__(
        self,
        manager: EventManager,
        event: str,
        handler: Handler,
        *,
        once: bool = False,
        condition: Condition | None = None,
    ) -> None:
        self._manager = manager
        self._event = event
        self._handler = handler
        self._once = once
        self._condition = condition
        # The signatures are checked once, at registration: a trigger gives the context to the
        # adapted callables.
        self._handler_call = adapt_call(handler, "handler")
        self._condition_call = None if condition is None else adapt_call(condition, "condition")
        # The condition is rejected now, not at the first trigger, which can be much later.
        if condition is not None and has_kind(condition, inspect.iscoroutinefunction):
            msg = f"condition must be synchronous, but got {describe(condition)}"
            raise TypeError(msg)
        # ``trigger_event`` cannot run a coroutine function: it is detected now, so that the
        # trigger is rejected before anything runs.
        self._is_async = has_kind(handler, inspect.iscoroutinefunction)
        # A trigger only calls ``_claim`` for these registrations: the others save a method call.
        self._guarded = bool(once) or condition is not None
        # Only the manager changes it, under its lock: True while the registration is in its
        # registry.
        self._active = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.remove()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}"
            f"(event={self._event!r}, handler={describe(self._handler)!r})"
        )

    def __reduce__(self) -> NoReturn:
        msg = f"{type(self).__qualname__} cannot be copied or pickled: register the handler again"
        raise TypeError(msg)

    @property
    def event(self) -> str:
        r"""Get the event name of the registration.

        Returns:
            The event name.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.add_event_handler("epoch_end", lambda: None).event
            'epoch_end'

            ```
        """
        return self._event

    @property
    def handler(self) -> Handler:
        r"""Get the registered handler.

        Returns:
            The handler given to ``add_event_handler``.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> def handler() -> None: ...
            >>> manager.add_event_handler("epoch_end", handler).handler is handler
            True

            ```
        """
        return self._handler

    @property
    def once(self) -> bool:
        r"""Indicate if the registration is removed just before its first
        execution.

        Returns:
            ``True`` if the event handler runs at most once, otherwise
                ``False``.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.add_event_handler("epoch_end", lambda: None, once=True).once
            True

            ```
        """
        return self._once

    @property
    def condition(self) -> Condition | None:
        r"""Get the condition evaluated before the handler.

        Returns:
            The condition, or ``None`` if the handler always runs.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> print(manager.add_event_handler("epoch_end", lambda: None).condition)
            None

            ```
        """
        return self._condition

    @property
    def active(self) -> bool:
        r"""Indicate if the registration is still registered.

        Returns:
            ``True`` exactly while the registration is in the manager:
                it becomes ``False`` when the registration is removed, by
                whatever means (``remove``, ``clear_event``, ``reset`` or
                the claim of a ``once`` registration).

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("epoch_end", lambda: None)
            >>> subscription.active
            True
            >>> manager.reset()
            >>> subscription.active
            False

            ```
        """
        return self._active

    def _claim(self, context: Context) -> bool:
        r"""Decide if a trigger calls the handler: condition, removal, then
        once claim.

        A registration that its condition removed is not called. The claim of
        a ``once`` registration is its atomic removal, so one caller only gets
        ``True``. A condition that is ``False`` (or that raises) does not
        consume the registration.

        Args:
            context: The context of the trigger, given to a condition that
                needs it.

        Returns:
            ``True`` if the handler must be called, ``False`` if the
                condition is ``False``, if the registration is removed (by its
                condition or by another thread) or if it lost the claim.

        Raises:
            TypeError: if the condition returns an awaitable (a coroutine is
                closed). Any exception of the condition also propagates. Both
                have a note that names the condition and the handler.

        Example:
            ```pycon
            >>> from minevent import Context, EventManager
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("my_event", lambda: None, once=True)
            >>> subscription._claim(Context()), subscription._claim(Context())
            (True, False)

            ```
        """
        if self._condition_call is not None:
            try:
                result = self._condition_call(context)
                # A coroutine is truthy: a condition that returns one would always run the handler.
                if result is not True and result is not False:
                    msg = f"condition {describe(self._condition)} returned an awaitable"
                    reject_awaitable(result, msg)
                if not result:
                    return False
            except Exception as exc:
                condition = describe(self._condition)
                source = f"the condition {condition} of {describe(self._handler)}"
                add_error_note(exc, source, self._event)
                raise
        return self.remove() if self._once else self._active

    def remove(self) -> bool:
        r"""Remove this registration.

        It never raises, and its cost does not depend on the number of
        handlers of the event.

        Returns:
            ``True`` if the registration was removed, ``False`` if it was
                already removed.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("epoch_end", lambda: None)
            >>> subscription.remove()
            True
            >>> subscription.remove()
            False

            ```
        """
        return self._manager._remove(self)


class EventManager:
    r"""Implement an event manager.

    ``add_event_handler`` registers a handler to an event, a
    case-sensitive string, and returns the ``Subscription`` that removes
    it. The ``on`` decorator registers the function that it decorates.
    ``trigger_event`` and ``atrigger_event`` run the handlers of an event
    in the order they were added, and ``clear_event`` and ``reset``
    remove registrations. ``events``, ``get_subscriptions``,
    ``event in manager`` and ``len(manager)`` (the number of
    registrations) read the registry, which is thread-safe. A manager is
    always truthy. Copying or pickling it raises a ``TypeError``. The
    guarantees and the limits are in the "How It Works" page of the
    documentation, and the reasons in its "Design Choices" page.

    Example:
        ```pycon
        >>> from minevent import EventManager
        >>> manager = EventManager()
        >>> _ = manager.add_event_handler("my_event", lambda: print("Hello!"))
        >>> manager.trigger_event("my_event")
        Hello!
        >>> manager
        EventManager(events={'my_event': 1})

        ```
    """

    def __init__(self) -> None:
        # This variable is used to store the registrations of each event, in the order they run.
        # A dict is an ordered set: the keys keep the registration order and removing is O(1).
        self._subscriptions: dict[str, dict[Subscription, None]] = {}
        # This lock protects the state above. The handlers run without it. It is reentrant, so a
        # signal handler or a finalizer that runs while it is held can use the manager.
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        with self._lock:
            events = {event: len(subs) for event, subs in self._subscriptions.items()}
        return f"{self.__class__.__qualname__}(events={events})"

    def __contains__(self, event: object) -> bool:
        with self._lock:
            return event in self._subscriptions

    def __len__(self) -> int:
        with self._lock:
            return sum(len(subs) for subs in self._subscriptions.values())

    def __bool__(self) -> bool:
        return True

    def __reduce__(self) -> NoReturn:
        msg = f"{type(self).__qualname__} cannot be copied or pickled: create a new one"
        raise TypeError(msg)

    @property
    def events(self) -> list[str]:
        r"""Get the events that have at least one registered handler.

        Returns:
            The event names, in the order they were first registered.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.events
            []
            >>> _ = manager.add_event_handler("my_event", lambda: None)
            >>> manager.events
            ['my_event']
            >>> "my_event" in manager
            True

            ```
        """
        with self._lock:
            return list(self._subscriptions)

    def get_subscriptions(self, event: str) -> tuple[Subscription, ...]:
        r"""Get the subscriptions registered for an event.

        Args:
            event: The event name (case-sensitive string).

        Returns:
            A snapshot of the subscriptions, in the order the handlers
                run. It is empty if no handler is registered. Use the
                ``handler`` property of a subscription to get its
                handler. Changing the manager does not change the
                returned tuple.

        Raises:
            TypeError: if ``event`` is not a string.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.get_subscriptions("my_event")
            ()
            >>> def handler():
            ...     print("Hello!")
            ...
            >>> subscription = manager.add_event_handler("my_event", handler)
            >>> manager.get_subscriptions("my_event") == (subscription,)
            True
            >>> subscription.handler is handler
            True
            >>> len(manager)
            1

            ```
        """
        _check_event(event)
        with self._lock:
            return tuple(self._subscriptions.get(event, ()))

    def add_event_handler(
        self,
        event: str,
        handler: Handler,
        *,
        once: bool = False,
        condition: Condition | None = None,
    ) -> Subscription:
        r"""Add a handler to an event.

        Each trigger of the event calls the handler after the handlers added
        before it, as ``handler()``, or as ``handler(context)`` with the
        read-only ``Context`` of the trigger if it has one parameter without
        default. ``minevent.calls.adapt_call`` states the whole rule. Use
        a function, a lambda or a ``functools.partial`` to give other
        arguments.

        Args:
            event: The event name (case-sensitive string).
            handler: The callable to attach to the event (``Handler``).
            once: If ``True``, the registration is removed just before the
                first call of the handler, so it runs at most once, even when
                several threads trigger the event. A condition that is
                ``False`` does not consume it. Default is ``False``.
            condition: A synchronous function that returns a boolean, called
                like a handler before it: the handler runs only if the result
                is true. A stateful condition, such as ``PeriodicCondition``,
                must not be shared between registrations. If ``None``, the
                handler always runs. Default is ``None``.

        Returns:
            A subscription whose ``remove`` method removes this registration
                only.

        Raises:
            TypeError: if ``event`` is not a string, if ``handler`` is not
                callable, if ``condition`` is neither ``None`` nor callable, if
                ``once`` is not a ``bool``, if ``handler`` or ``condition`` is
                a generator function, needs another argument than the context,
                or has a signature that cannot be inspected, or if
                ``condition`` is a coroutine function. A callable object is
                judged by its ``__call__``. The manager is unchanged.

        Example:
            ```pycon
            >>> from minevent import EventManager, PeriodicCondition
            >>> manager = EventManager()
            >>> _ = manager.add_event_handler(
            ...     "epoch_end",
            ...     lambda context: print(f"epoch {context['epoch']}"),
            ...     condition=PeriodicCondition(freq=2),
            ... )
            >>> _ = manager.add_event_handler("epoch_end", lambda: print("first"), once=True)
            >>> manager.trigger_event("epoch_end", {"epoch": 0})
            epoch 0
            first
            >>> manager.trigger_event("epoch_end", {"epoch": 1})
            >>> manager.trigger_event("epoch_end", {"epoch": 2})
            epoch 2

            ```
        """
        _check_event(event)
        if not callable(handler):
            msg = f"handler must be callable, but got {reprlib.repr(handler)}"
            raise TypeError(msg)
        if condition is not None and not callable(condition):
            msg = f"condition must be callable, but got {reprlib.repr(condition)}"
            raise TypeError(msg)
        if not isinstance(once, bool):
            msg = f"once must be a bool, but got {type(once).__qualname__}"
            raise TypeError(msg)
        subscription = Subscription(self, event, handler, once=once, condition=condition)
        with self._lock:
            self._subscriptions.setdefault(event, {})[subscription] = None
            subscription._active = True
        return subscription

    def on(
        self,
        event: str,
        *,
        once: bool = False,
        condition: Condition | None = None,
    ) -> Callable[[_F], _F]:
        r"""Create a decorator that registers a function as a handler.

        The decorated function is registered with
        ``add_event_handler(event, func, once=once, condition=condition)``
        and returned unchanged. Use ``add_event_handler`` if you need the
        ``Subscription``.

        Args:
            event: The event name (case-sensitive string).
            once: See ``add_event_handler``. Default is ``False``.
            condition: See ``add_event_handler``. Default is ``None``.

        Returns:
            The decorator.

        Raises:
            TypeError: if ``event`` is not a string, or, when the decorator is
                applied, if ``add_event_handler`` rejects the decorated object,
                ``once`` or the condition.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> @manager.on("my_event")
            ... def hello_handler(context):
            ...     print(f"Hello {context['name']}!")
            ...
            >>> manager.trigger_event("my_event", {"name": "Bob"})
            Hello Bob!
            >>> hello_handler({"name": "Alice"})
            Hello Alice!

            ```
        """
        _check_event(event)

        def decorator(func: _F) -> _F:
            r"""Register ``func`` and return it unchanged (see
            ``on``)."""
            self.add_event_handler(event, func, once=once, condition=condition)
            return func

        return decorator

    def _remove(self, subscription: Subscription) -> bool:
        r"""Remove one registration.

        Args:
            subscription: The registration to remove.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("epoch_end", lambda: None)
            >>> manager._remove(subscription), manager._remove(subscription)
            (True, False)

            ```
        """
        with self._lock:
            subs = self._subscriptions.get(subscription.event)
            if subs is None or subscription not in subs:
                return False
            del subs[subscription]
            subscription._active = False
            if not subs:
                del self._subscriptions[subscription.event]
        return True

    def trigger_event(self, event: str, context: Mapping[str, object] | None = None, /) -> None:
        r"""Run the handlers of an event, in the order they were added.

        The handlers registered when the trigger starts run one after the
        other, and a registration removed before its handler is called, even
        by its own condition, does not run. The condition of a registration is
        evaluated just before its handler.
        No handler runs if the event has none. The trigger is fail-fast:
        an exception of a handler or a condition propagates unwrapped, with a
        note that says what raised it, and the next handlers are skipped.
        If one of the registrations has a coroutine function as handler (a
        callable object is judged by its ``__call__``), the trigger is
        rejected before any condition or handler runs.

        Args:
            event: The event name (case-sensitive string) to trigger.
            context: The data of the trigger: a mapping from ``str`` to values,
                a ``Context`` or ``None`` (no data). A mapping is copied into
                one read-only ``Context`` shared by the handlers and the
                conditions, and a ``Context`` is used as is. Default is
                ``None``.

        Raises:
            TypeError: if ``event`` is not a string, if ``context`` is neither
                ``None`` nor a mapping with ``str`` keys, if a handler is a
                coroutine function (nothing runs, use ``atrigger_event``), or if
                a condition or a handler returns an awaitable. Any exception of a
                handler or a condition also propagates.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.trigger_event("epoch_end")  # no handler: nothing happens
            >>> _ = manager.add_event_handler(
            ...     "epoch_end", lambda context: print(f"epoch {context['epoch']}")
            ... )
            >>> manager.trigger_event("epoch_end", {"epoch": 3})
            epoch 3

            ```
        """
        subscriptions = self.get_subscriptions(event)
        context = _as_context(context)
        # A first pass rejects the trigger as a whole, whatever the conditions would answer.
        for subscription in subscriptions:
            if subscription._is_async:
                name = describe(subscription.handler)
                msg = (
                    f"{name} is a coroutine function; use atrigger_event for the event "
                    f"{describe_event(event)}"
                )
                raise TypeError(msg)
        for subscription in subscriptions:
            if not subscription._active or (
                subscription._guarded and not subscription._claim(context)
            ):
                continue
            try:
                result = subscription._handler_call(context)
                if result is not None and isinstance(result, Awaitable):
                    name = describe(subscription.handler)
                    msg = f"{name} returned an awaitable; use atrigger_event"
                    reject_awaitable(result, msg)
            except Exception as exc:
                add_error_note(exc, describe(subscription.handler), event)
                raise

    async def atrigger_event(
        self, event: str, context: Mapping[str, object] | None = None, /
    ) -> None:
        r"""Run the handlers of an event, awaiting the coroutine handlers.

        It behaves like ``trigger_event``, but the awaitable that a handler
        returns is awaited before the next handler. A synchronous handler
        blocks the event loop while it runs.

        Args:
            event: The event name (case-sensitive string) to trigger.
            context: The data of the trigger, as in ``trigger_event``. Default
                is ``None``.

        Raises:
            TypeError: if ``event`` is not a string, if ``context`` is neither
                ``None`` nor a mapping with ``str`` keys, or if a condition
                returns an awaitable (a condition is never awaited). Any
                exception of a handler or a condition also propagates.

        Example:
            ```pycon
            >>> import asyncio
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> async def hello_handler(context):
            ...     print(f"Hello {context['name']}!")
            ...
            >>> _ = manager.add_event_handler("my_event", hello_handler)
            >>> asyncio.run(manager.atrigger_event("my_event", {"name": "John"}))
            Hello John!

            ```
        """
        subscriptions = self.get_subscriptions(event)
        context = _as_context(context)
        for subscription in subscriptions:
            if not subscription._active or (
                subscription._guarded and not subscription._claim(context)
            ):
                continue
            try:
                result = subscription._handler_call(context)
                if result is not None and isinstance(result, Awaitable):
                    await result
            except Exception as exc:
                add_error_note(exc, describe(subscription.handler), event)
                raise

    def clear_event(self, event: str) -> None:
        r"""Remove all the registrations of an event.

        Nothing happens if the event has no handler. The removed handlers are
        released outside the lock, so their finalizers can use the manager.

        Args:
            event: The event name (case-sensitive string) to clear.

        Raises:
            TypeError: if ``event`` is not a string.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> _ = manager.add_event_handler("my_event", lambda: None)
            >>> manager.clear_event("my_event")
            >>> manager.events
            []

            ```
        """
        _check_event(event)
        with self._lock:
            removed = self._subscriptions.pop(event, {})
            for subscription in removed:
                subscription._active = False
        # The handlers are released when this method returns, without the lock, so their
        # finalizers can use the manager.

    def reset(self) -> None:
        r"""Remove all the registrations of all the events.

        The removed handlers are released outside the lock, so their
        finalizers can use the manager.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> _ = manager.add_event_handler("my_event", lambda: None)
            >>> manager.reset()
            >>> len(manager)
            0

            ```
        """
        with self._lock:
            removed, self._subscriptions = self._subscriptions, {}
            for subs in removed.values():
                for subscription in subs:
                    subscription._active = False
        # The handlers are released when this method returns, without the lock, so their
        # finalizers can use the manager.
