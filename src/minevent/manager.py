r"""Implement the event manager."""

from __future__ import annotations

__all__ = ["EventManager", "Subscription"]

import logging
import threading
from typing import TYPE_CHECKING, NoReturn, Self, TypeVar

from minevent.handlers import BaseEventHandler, EventHandler

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from minevent.conditions import Condition

_F = TypeVar("_F", bound="Callable[..., object]")

logger: logging.Logger = logging.getLogger(__name__)


def _check_event(event: object) -> None:
    r"""Check that an event name is a string.

    Args:
        event: The event name to check.

    Raises:
        TypeError: if ``event`` is not a ``str``.
    """
    if not isinstance(event, str):
        msg = f"event must be a str, but got {type(event).__qualname__}"
        raise TypeError(msg)


def _describe(event_handler: BaseEventHandler) -> str:
    r"""Name an event handler without calling the ``repr`` of its data.

    The ``repr`` of an event handler contains its arguments, which can
    be large or raise, so it is not used in the note of an exception.

    Args:
        event_handler: The event handler to name.

    Returns:
        The qualified name of the function of an ``EventHandler``, or
            the name of the class of the callable if it has no name
            (for example a ``functools.partial``), or the name of the
            class of any other event handler.

    Example:
        ```pycon
        >>> from minevent import EventHandler
        >>> from minevent.manager import _describe
        >>> _describe(EventHandler(print))
        'print'

        ```
    """
    target = event_handler.handler if isinstance(event_handler, EventHandler) else event_handler
    return getattr(target, "__qualname__", type(target).__qualname__)


def _add_error_note(exc: Exception, event: str, event_handler: BaseEventHandler) -> None:
    r"""Add a note to the exception raised by an event handler.

    The note names the event and the function of the handler, never
    its arguments. The note is not added if the exception already has
    it, so an exception instance that is raised again (or a handler
    that triggers its own event) has one note per distinct pair of
    event and handler.

    Args:
        exc: The exception raised by the event handler.
        event: The event that was triggered.
        event_handler: The event handler that raised the exception.
    """
    note = f"raised by {_describe(event_handler)} while handling the event {event!r}"
    if note not in getattr(exc, "__notes__", ()):
        exc.add_note(note)


class Subscription:
    r"""Represent the registration of an event handler to an event.

    A subscription is returned by ``EventManager.add_event_handler``.
    It is the registration itself: the manager stores it, and it
    removes exactly the registration that created it. The handler does
    not need to be re-created to be unsubscribed, other registrations
    of the same handler are not removed, and registering the same
    handler twice creates two independent subscriptions.

    A subscription is a context manager: the registration is removed
    when the ``with`` block exits.

    The constructor is internal: subscriptions are created by the
    event manager.

    Args:
        manager: The event manager that stores the registration.
        event: The event name of the registration.
        event_handler: The registered event handler.
        once: If ``True``, the registration is removed before its
            first execution. Default is ``False``.

    Example:
        ```pycon
        >>> from minevent import EventHandler, EventManager
        >>> manager = EventManager()
        >>> subscription = manager.add_event_handler("my_event", EventHandler(print))
        >>> subscription.event
        'my_event'
        >>> subscription.active
        True
        >>> subscription.remove()
        True
        >>> subscription.remove()
        False
        >>> subscription.active
        False
        >>> manager.events
        []
        >>> with manager.add_event_handler("my_event", EventHandler(print)):
        ...     manager.events
        ...
        ['my_event']
        >>> manager.events
        []

        ```
    """

    def __init__(
        self,
        manager: EventManager,
        event: str,
        event_handler: BaseEventHandler,
        *,
        once: bool = False,
    ) -> None:
        self._manager = manager
        self._event = event
        self._event_handler = event_handler
        self._once = once

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
        return f"{self.__class__.__qualname__}(event={self._event!r})"

    @property
    def event(self) -> str:
        r"""Get the event name of the registration.

        Returns:
            The event name.
        """
        return self._event

    @property
    def event_handler(self) -> BaseEventHandler:
        r"""Get the registered event handler.

        Returns:
            The event handler.
        """
        return self._event_handler

    @property
    def once(self) -> bool:
        r"""Indicate if the registration is removed before its first
        execution.

        Returns:
            ``True`` if the event handler runs at most once, otherwise
                ``False``.
        """
        return self._once

    @property
    def active(self) -> bool:
        r"""Indicate if the registration is still registered.

        Returns:
            ``True`` if the event handler is still registered,
                ``False`` if it was removed (by this subscription, by
                ``clear_event`` or ``reset``, or because it was a
                ``once`` registration consumed by a trigger), or if
                it was never registered in its manager. The answer
                is read from the registry of the manager.
        """
        return self._manager._is_registered(self)

    def remove(self) -> bool:
        r"""Remove the registration.

        Only this registration is removed, even if the same handler is
        registered several times to the same event. Calling this
        method again, or after the registration was removed another
        way (``clear_event``, ``reset``, a ``once`` trigger), does
        nothing. It never raises, even for a subscription that was
        never registered in its manager. The cost does not depend on
        the number of handlers of the event.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.
        """
        return self._manager._remove(self)


class EventManager:
    r"""Implement an event manager.

    This event manager allows registering event handlers and triggering
    events. An event is represented by a case-sensitive string. Each
    event can have multiple handlers attached, and all handlers are
    executed in the order they were added when the event is triggered.

    ``add_event_handler`` (or the ``on`` decorator) registers an event
    handler and returns a ``Subscription`` that removes that
    registration. ``trigger_event`` runs the handlers synchronously,
    and ``atrigger_event`` awaits the coroutine handlers. The manager
    has no global state: create one instance and pass it where it is
    needed. Registrations and triggers are logged at the ``DEBUG``
    level by the ``minevent.manager`` logger.

    Error policy: handlers run fail-fast. If a handler raises, the
    exception propagates to the caller of ``trigger_event`` (or
    ``atrigger_event``) and the remaining handlers of that event are
    not executed.

    Thread safety: the registration, removal and inspection of
    handlers are protected by a reentrant lock, and ``trigger_event``
    runs the handlers on a snapshot taken under the lock, outside of
    it. So handlers can be registered in one thread and events
    triggered from worker threads. The handlers themselves run in the
    thread that triggers the event, concurrently if several threads
    trigger the same event, so a handler that shares state must be
    thread-safe. The mutable state of a condition, such as the
    counter of ``PeriodicCondition``, is not protected.

    A manager is a service, not a collection: ``bool(manager)`` is
    always ``True``, even when it has no handler, so ``manager or
    default`` means "is there a manager". Use ``len(manager)`` for the
    number of registrations. A manager owns a lock and a registry, so
    it cannot be copied or pickled (``copy.copy``, ``copy.deepcopy`` and
    ``pickle`` raise a ``TypeError``): create a new one.

    Example:
        ```pycon
        >>> from minevent import EventHandler, EventManager
        >>> def hello_handler():
        ...     print("Hello!")
        ...
        >>> manager = EventManager()
        >>> bool(manager)
        True
        >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
        >>> manager.trigger_event("my_event")
        Hello!

        ```
    """

    def __init__(self) -> None:
        # This variable is used to store the registrations of each event, in the order they run.
        # A dict is an ordered set: the keys keep the registration order and removing is O(1).
        self._subscriptions: dict[str, dict[Subscription, None]] = {}
        # This lock protects the state above. It is reentrant, so a handler can use the manager.
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
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.events
            []
            >>> _ = manager.add_event_handler("my_event", EventHandler(print))
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
                ``event_handler`` property of a subscription to get its
                handler. Changing the manager does not change the
                returned tuple.

        Raises:
            TypeError: if ``event`` is not a string.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.get_subscriptions("my_event")
            ()
            >>> handler = EventHandler(print)
            >>> subscription = manager.add_event_handler("my_event", handler)
            >>> manager.get_subscriptions("my_event") == (subscription,)
            True
            >>> subscription.event_handler is handler
            True
            >>> len(manager)
            1

            ```
        """
        _check_event(event)
        with self._lock:
            return tuple(self._subscriptions.get(event, ()))

    def add_event_handler(
        self, event: str, event_handler: BaseEventHandler, *, once: bool = False
    ) -> Subscription:
        r"""Add an event handler to an event.

        The event handler will be called every time the specified event
        is triggered. Multiple handlers can be registered to the same
        event, and they will be executed in the order they were added.

        Args:
            event: The event name (case-sensitive string) to which
                the event handler should be attached.
            event_handler: The event handler instance to attach to the
                event.
            once: If ``True``, the handler is removed before its first
                execution, so it runs at most once. The registration
                is removed by the next trigger even if the condition
                of the handler is ``False`` and the handler function is
                not called. Default is ``False``.

        Returns:
            A subscription whose ``remove`` method removes this
                registration only.

        Raises:
            TypeError: if ``event`` is not a string, or if
                ``event_handler`` is not a ``BaseEventHandler``. Wrap a
                function with ``EventHandler``.

        Example:
            ```pycon
            >>> from minevent import EventManager, EventHandler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> subscription.remove()
            True
            >>> manager.trigger_event("my_event")
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.trigger_event("my_event")

            ```
        """
        _check_event(event)
        if not isinstance(event_handler, BaseEventHandler):
            msg = (
                "event_handler must be a BaseEventHandler, but got "
                f"{type(event_handler).__qualname__}: wrap a function with EventHandler(func)"
            )
            raise TypeError(msg)
        subscription = Subscription(self, event, event_handler, once=once)
        with self._lock:
            self._subscriptions.setdefault(event, {})[subscription] = None
        logger.debug("Added %s to event %s", event_handler, event)
        return subscription

    def on(
        self,
        event: str,
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> Callable[[_F], _F]:
        r"""Create a decorator that registers a function as a handler.

        The decorated function is registered as
        ``EventHandler(func, condition=condition,
        filter_payload=filter_payload)`` and returned unchanged. The
        function is called with the payload only: use
        ``add_event_handler`` if the handler needs ``handler_args`` or
        ``handler_kwargs``, or if you need the ``Subscription``.

        Args:
            event: The event name (case-sensitive string).
            once: If ``True``, the handler runs at most once. See
                ``add_event_handler``. Default is ``False``.
            condition: An optional condition evaluated before the
                handler. See ``EventHandler``. Default is ``None``.
            filter_payload: If ``True``, only the payload keys that
                the function accepts are passed to it. See
                ``EventHandler``. Default is ``False``.

        Returns:
            The decorator.

        Raises:
            TypeError: if ``event`` is not a string, or if
                ``condition`` is not callable.

        Example:
            ```pycon
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> @manager.on("my_event")
            ... def hello_handler(name):
            ...     print(f"Hello {name}!")
            ...
            >>> manager.trigger_event("my_event", name="Bob")
            Hello Bob!
            >>> hello_handler("Alice")
            Hello Alice!
            >>> @manager.on("epoch_end", filter_payload=True)
            ... def log_epoch(epoch):
            ...     print(f"epoch {epoch}")
            ...
            >>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
            epoch 3

            ```
        """
        _check_event(event)

        def decorator(func: _F) -> _F:
            handler = EventHandler(func, condition=condition, filter_payload=filter_payload)
            self.add_event_handler(event, handler, once=once)
            return func

        return decorator

    def _is_registered(self, subscription: Subscription) -> bool:
        r"""Indicate if a registration is in the registry.

        Args:
            subscription: The registration to look for.

        Returns:
            ``True`` if the registration is registered for its event
                in this manager, ``False`` otherwise.
        """
        with self._lock:
            return subscription in self._subscriptions.get(subscription.event, ())

    def _remove(self, subscription: Subscription) -> bool:
        r"""Remove one registration.

        Args:
            subscription: The registration to remove.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.
        """
        with self._lock:
            subs = self._subscriptions.get(subscription.event)
            if subs is None or subscription not in subs:
                return False
            del subs[subscription]
            if not subs:
                del self._subscriptions[subscription.event]
        logger.debug("Removed %s in '%s' event", subscription.event_handler, subscription.event)
        return True

    def trigger_event(self, event: str, /, **payload: object) -> None:
        r"""Trigger the handler(s) for the given event.

        This method executes all event handlers registered for the
        specified event in the order they were added. Nothing happens
        if no handler is registered.

        Handlers are executed fail-fast: if a handler raises, the
        exception propagates and the remaining handlers are skipped.
        The exception is not wrapped: it has a note (``__notes__``)
        with the event and the function of the handler that raised it.

        The handlers are read from a snapshot taken when the event is
        triggered. Handlers added or removed by a running handler
        take effect on the next trigger, not the current one. A
        ``once`` registration is removed just before its handler runs.

        A handler can trigger events, including the event it handles,
        but nothing stops the recursion: a handler that always
        triggers its own event raises a ``RecursionError``. Guard the
        recursive trigger with a condition or a flag.

        The keyword arguments ``payload`` are passed to every
        handler as keyword arguments, after the arguments given at
        registration. Without payload, handlers are called exactly as
        before. A handler that does not accept the payload raises a
        ``TypeError``. The payload can use any key, including
        ``event`` and ``self``, because ``event`` is positional-only.

        Args:
            event: The event name (case-sensitive string) to trigger.
            **payload: The data passed to the handlers as keyword
                arguments.

        Raises:
            TypeError: if ``event`` is not a string, or if a handler
                returns an awaitable (use ``atrigger_event`` for
                coroutine handlers). Any exception raised by a
                handler also propagates.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.trigger_event("my_event")  # do nothing because there is no event handler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> def epoch_handler(epoch):
            ...     print(f"epoch {epoch}")
            ...
            >>> _ = manager.add_event_handler("epoch_end", EventHandler(epoch_handler))
            >>> manager.trigger_event("epoch_end", epoch=3)
            epoch 3

            ```
        """
        subscriptions = self.get_subscriptions(event)
        logger.debug("Firing %s event", event)
        for subscription in subscriptions:
            if subscription._once and not self._remove(subscription):
                continue
            try:
                subscription._event_handler.handle(**payload)
            except Exception as exc:
                _add_error_note(exc, event, subscription._event_handler)
                raise

    async def atrigger_event(self, event: str, /, **payload: object) -> None:
        r"""Trigger the handler(s) for the given event, awaiting the
        coroutine handlers.

        This method behaves like ``trigger_event``, but it calls
        ``ahandle`` on the event handlers, so handlers that are
        coroutine functions (or return an awaitable) are awaited.
        Synchronous handlers can be mixed with coroutine handlers.
        The handlers run one after the other, in the order they were
        added, and they are fail-fast like in ``trigger_event``: the
        exception is not wrapped and has a note with the event and the
        handler. The snapshot of the handlers, the ``once``
        registrations and the payload follow the rules of
        ``trigger_event``. Synchronous handlers block the event loop
        while they run.

        Args:
            event: The event name (case-sensitive string) to trigger.
            **payload: The data passed to the handlers as keyword
                arguments.

        Raises:
            TypeError: if ``event`` is not a string. Any exception
                raised by a handler also propagates.

        Example:
            ```pycon
            >>> import asyncio
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> async def hello_handler(name):
            ...     print(f"Hello {name}!")
            ...
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> asyncio.run(manager.atrigger_event("my_event", name="John"))
            Hello John!

            ```
        """
        subscriptions = self.get_subscriptions(event)
        logger.debug("Firing %s event", event)
        for subscription in subscriptions:
            if subscription._once and not self._remove(subscription):
                continue
            try:
                await subscription._event_handler.ahandle(**payload)
            except Exception as exc:
                _add_error_note(exc, event, subscription._event_handler)
                raise

    def clear_event(self, event: str) -> None:
        r"""Remove all the event handlers of a given event.

        Nothing happens if the event has no registered handler. The
        subscriptions of the removed handlers become inactive.

        Args:
            event: The event name (case-sensitive string) to clear.

        Raises:
            TypeError: if ``event`` is not a string.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> _ = manager.add_event_handler("my_event", EventHandler(print))
            >>> manager.clear_event("my_event")
            >>> manager.events
            []

            ```
        """
        _check_event(event)
        with self._lock:
            removed = self._subscriptions.pop(event, None)
        if removed is not None:
            logger.debug("Cleared all the event handlers of '%s' event", event)

    def reset(self) -> None:
        r"""Reset the event manager.

        This method removes all registered event handlers from the
        event manager, so their subscriptions become inactive. After
        calling this method, the event manager returns to its initial
        state.

        Example:
            ```pycon
            >>> # Create an event manager
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> # Add an event handler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> from minevent import EventHandler
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> len(manager)
            1
            >>> # Reset the event manager
            >>> manager.reset()
            >>> len(manager)
            0

            ```
        """
        with self._lock:
            self._subscriptions.clear()
