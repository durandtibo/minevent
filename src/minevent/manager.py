r"""Implement the event manager."""

from __future__ import annotations

__all__ = ["EventManager"]

import logging
import threading
from typing import TYPE_CHECKING, TypeVar

from coola.utils.format import str_indent, str_mapping, str_sequence

from minevent.handlers import BaseEventHandler, EventHandler
from minevent.subscription import Subscription

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_F = TypeVar("_F", bound="Callable[..., object]")

logger: logging.Logger = logging.getLogger(__name__)


def _check_event(event: object) -> None:
    r"""Check that an event name is a string.

    Raises:
        TypeError: if ``event`` is not a ``str``.
    """
    if not isinstance(event, str):
        msg = f"event must be a str, but got {type(event).__qualname__}"
        raise TypeError(msg)


class EventManager:
    r"""Implement an event manager.

    This event manager allows registering event handlers and triggering
    events. An event is represented by a case-sensitive string. Each
    event can have multiple handlers attached, and all handlers are
    executed in the order they were added when the event is triggered.
    The manager also tracks the last triggered event. This is
    informational: it is meaningful in single-threaded code, and with
    several threads it is the event of whichever trigger started last.

    Error policy: handlers run fail-fast. If a handler raises, the
    exception propagates to the caller of ``trigger_event`` and the
    remaining handlers of that event are not executed.

    Thread safety: the registration, removal and inspection of
    handlers are protected by a reentrant lock, and ``trigger_event``
    runs the handlers on a snapshot taken under the lock, outside of
    it. So handlers can be registered in one thread and events
    triggered from worker threads. The handlers themselves run in the
    thread that triggers the event, concurrently if several threads
    trigger the same event, so a handler that shares state must be
    thread-safe. The mutable state of a condition, such as the
    counter of ``PeriodicCondition``, is not protected.

    Example:
        ```pycon
        >>> from minevent import EventHandler, EventManager
        >>> def hello_handler():
        ...     print("Hello!")
        ...
        >>> manager = EventManager()
        >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
        >>> manager.trigger_event("my_event")
        Hello!

        ```
    """

    def __init__(self) -> None:
        # This variable is used to store the registrations of each event, in the order they run.
        self._subscriptions: dict[str, list[Subscription]] = {}
        # This variable is used to track the last fired event name
        self._last_triggered_event: str | None = None
        # This lock protects the state above. It is reentrant, so a handler can use the manager.
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        with self._lock:
            event_handlers = {
                event: tuple(sub.event_handler for sub in subs)
                for event, subs in self._subscriptions.items()
            }
            last_triggered_event = self._last_triggered_event
        # The handlers can have a custom repr, so they are formatted outside of the lock.
        config = {
            "event_handlers": self._format_event_handlers(event_handlers),
            "last_triggered_event": last_triggered_event,
        }
        args = str_indent(str_mapping(config))
        return f"{self.__class__.__qualname__}(\n  {args}\n)"

    @staticmethod
    def _format_event_handlers(event_handlers: Mapping[str, Sequence[BaseEventHandler]]) -> str:
        r"""Format the registered handlers, one block per event.

        Args:
            event_handlers: The handlers of each event.

        Returns:
            The formatted handlers, starting with a newline, or
                ``"{}"`` if no handler is registered.
        """
        if not event_handlers:
            return "{}"
        return "\n" + str_mapping(
            {event: "\n" + str_sequence(handlers) for event, handlers in event_handlers.items()}
        )

    def __contains__(self, event: object) -> bool:
        with self._lock:
            return event in self._subscriptions

    def __len__(self) -> int:
        with self._lock:
            return sum(len(subs) for subs in self._subscriptions.values())

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

    @property
    def last_triggered_event(self) -> str | None:
        r"""Get the last event name that was triggered.

        The name is recorded when the dispatch starts, before any
        handler runs. It is therefore already updated when a handler
        reads it, and it is kept even if a handler raises. It is
        informational: if several threads trigger events, it is the
        event of the trigger that started last.

        Returns:
            The last event name that was triggered, or ``None`` if no event
                was fired.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.last_triggered_event
            'my_event'

            ```
        """
        with self._lock:
            return self._last_triggered_event

    def get_event_handlers(self, event: str) -> tuple[BaseEventHandler, ...]:
        r"""Get the event handlers registered for an event.

        Args:
            event: The event name (case-sensitive string).

        Returns:
            A snapshot of the event handlers, in the order they were
                added. It is empty if no handler is registered. The
                handlers added with ``once=True`` are returned
                as registered. Changing the manager does not change the
                returned tuple.

        Raises:
            TypeError: if ``event`` is not a string.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.get_event_handlers("my_event")
            ()
            >>> handler = EventHandler(print)
            >>> _ = manager.add_event_handler("my_event", handler)
            >>> manager.get_event_handlers("my_event") == (handler,)
            True
            >>> len(manager)
            1

            ```
        """
        _check_event(event)
        with self._lock:
            return tuple(sub.event_handler for sub in self._subscriptions.get(event, ()))

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
                execution, so it runs at most once. It is still found
                by ``has_event_handler`` and ``remove_event_handler``
                until then. The registration is removed by the next
                trigger even if the condition of the handler is
                ``False`` and the handler function is not called.
                Default is ``False``.

        Returns:
            A subscription whose ``remove`` method removes this
                registration only.

        Raises:
            TypeError: if ``event`` is not a string.

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
        subscription = Subscription(self, event, event_handler, once=once)
        with self._lock:
            self._subscriptions.setdefault(event, []).append(subscription)
        logger.debug("Added %s to event %s", event_handler, event)
        return subscription

    def on(self, event: str, *, once: bool = False) -> Callable[[_F], _F]:
        r"""Create a decorator that registers a function as a handler.

        The decorated function is registered as
        ``EventHandler(func)`` and returned unchanged. Use
        ``add_event_handler`` if the handler needs arguments or a
        condition, or if you need the ``Subscription``.

        Args:
            event: The event name (case-sensitive string).
            once: If ``True``, the handler runs at most once. See
                ``add_event_handler``. Default is ``False``.

        Returns:
            The decorator.

        Raises:
            TypeError: if ``event`` is not a string.

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

            ```
        """
        _check_event(event)

        def decorator(func: _F) -> _F:
            self.add_event_handler(event, EventHandler(func), once=once)
            return func

        return decorator

    def _remove(self, subscription: Subscription) -> bool:
        r"""Remove one registration.

        Args:
            subscription: The registration to remove.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.
        """
        with self._lock:
            if not subscription.active:
                return False
            subscription._active = False
            subs = self._subscriptions[subscription.event]
            subs.remove(subscription)
            if not subs:
                del self._subscriptions[subscription.event]
        logger.debug("Removed %s in '%s' event", subscription.event_handler, subscription.event)
        return True

    def _claim(self, subscription: Subscription) -> bool:
        r"""Claim the right to run a registration.

        Args:
            subscription: A registration of the snapshot of a trigger.

        Returns:
            ``True`` if the event handler can run: the registration
                is not ``once``, or this call removed it. ``False`` if
                another call already removed a ``once`` registration.
        """
        return not subscription.once or self._remove(subscription)

    def trigger_event(self, event: str, /, **payload: object) -> None:
        r"""Trigger the handler(s) for the given event.

        This method executes all event handlers registered for the
        specified event in the order they were added. The last
        triggered event name is updated regardless of whether any
        handlers are registered.

        Handlers are executed fail-fast: if a handler raises, the
        exception propagates and the remaining handlers are skipped.

        The handlers are read from a snapshot taken when the event is
        triggered. Handlers added or removed by a running handler
        take effect on the next trigger, not the current one.

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
            TypeError: if ``event`` is not a string.

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
        for subscription in self._start_trigger(event):
            if self._claim(subscription):
                subscription.event_handler.handle(**payload)

    async def atrigger_event(self, event: str, /, **payload: object) -> None:
        r"""Trigger the handler(s) for the given event, awaiting the
        coroutine handlers.

        This method behaves like ``trigger_event``, but it calls
        ``ahandle`` on the event handlers, so handlers that are
        coroutine functions (or return an awaitable) are awaited.
        Synchronous handlers can be mixed with coroutine handlers.
        The handlers run one after the other, in the order they were
        added, and they are fail-fast like in ``trigger_event``.

        Args:
            event: The event name (case-sensitive string) to trigger.
            **payload: The data passed to the handlers as keyword
                arguments.

        Raises:
            TypeError: if ``event`` is not a string.

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
        for subscription in self._start_trigger(event):
            if self._claim(subscription):
                await subscription.event_handler.ahandle(**payload)

    def _start_trigger(self, event: str) -> tuple[Subscription, ...]:
        r"""Record a trigger and return the handlers to run.

        Args:
            event: The event name.

        Returns:
            A snapshot of the registrations of the event.

        Raises:
            TypeError: if ``event`` is not a string.
        """
        _check_event(event)
        logger.debug("Firing %s event", event)
        with self._lock:
            self._last_triggered_event = event
            return tuple(self._subscriptions.get(event, ()))

    def has_event_handler(
        self, event_handler: BaseEventHandler | Subscription, event: str | None = None
    ) -> bool:
        r"""Indicate if a handler is registered in the event manager.

        This method checks whether a specific event handler is
        registered, either for a specific event or across all events.
        Note that this method relies on the ``equal`` method of the
        input event handler to compare event handlers. Lambdas,
        closures and bound methods of different instances are usually
        not equal, so prefer passing the ``Subscription`` returned by
        ``add_event_handler``: it matches exactly that registration.

        Args:
            event_handler: The event handler instance, or the
                subscription, to search for in the registered
                handlers.
            event: An event name (case-sensitive string) to check. If
                ``None``, the method will search across all registered
                events. Default is ``None``.

        Raises:
            TypeError: if ``event`` is neither ``None`` nor a string.

        Returns:
            ``True`` if a matching event handler is registered,
                otherwise ``False``.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager = EventManager()
            >>> # Check if `hello_handler` is registered in the event manager
            >>> manager.has_event_handler(EventHandler(hello_handler))
            False
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            False
            >>> # Add an event handler
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager
            >>> manager.has_event_handler(EventHandler(hello_handler))
            True
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            True
            >>> # Check if `hello_handler` is registered in the event manager for 'my_other_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_other_event")
            False

            ```
        """
        if event is not None:
            _check_event(event)
        if isinstance(event_handler, Subscription):
            if event is not None and event != event_handler.event:
                return False
            return event_handler.active and event_handler._manager is self
        with self._lock:
            events = list(self._subscriptions) if event is None else [event]
            registered = [tuple(self._subscriptions.get(evnt, ())) for evnt in events]
        return any(event_handler.equal(sub.event_handler) for subs in registered for sub in subs)

    def remove_event_handler(
        self,
        event: str,
        event_handler: BaseEventHandler | Subscription,
        *,
        missing_ok: bool = False,
    ) -> None:
        r"""Remove an event handler of a given event.

        This method removes all occurrences of the specified event
        handler from the given event. If the same event handler was
        added multiple times to the event, all duplicates are removed.
        This method relies on the ``equal`` method of the input event
        handler to compare event handlers. Lambdas, closures and bound
        methods of different instances are usually not equal, so
        prefer passing the ``Subscription`` returned by
        ``add_event_handler``: it removes exactly that registration.

        Args:
            event: The event name (case-sensitive string) from which
                the handler should be removed.
            event_handler: The event handler instance, or the
                subscription, to remove from the event.
            missing_ok: If ``True``, do nothing when the event does
                not exist or the handler is not attached to it,
                instead of raising an exception. Default is ``False``.

        Raises:
            TypeError: if ``event`` is not a string.
            ValueError: if the event does not exist or if the
                handler is not attached to the event, and
                ``missing_ok`` is ``False``.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            True
            >>> # Remove the event handler
            >>> manager.remove_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            False

            ```
        """
        _check_event(event)
        if isinstance(event_handler, Subscription):
            if (
                event_handler.event == event
                and event_handler._manager is self
                and event_handler.remove()
            ):
                return
            if missing_ok:
                return
            msg = (
                f"{event_handler} is not found among registered event handlers for '{event}' event"
            )
            raise ValueError(msg)
        with self._lock:
            registered = tuple(self._subscriptions.get(event, ()))
        if not registered:
            if missing_ok:
                return
            msg = f"'{event}' event does not exist"
            raise ValueError(msg)

        # The comparison can run user code, so it is done outside of the lock.
        matches = [sub for sub in registered if event_handler.equal(sub.event_handler)]
        if not matches:
            if missing_ok:
                return
            msg = (
                f"{event_handler} is not found among registered event handlers for '{event}' event"
            )
            raise ValueError(msg)
        for sub in matches:
            sub.remove()

    def clear_event(self, event: str) -> None:
        r"""Remove all the event handlers of a given event.

        Nothing happens if the event has no registered handler.

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
            for sub in removed or ():
                sub._active = False
        if removed is not None:
            logger.debug("Cleared all the event handlers of '%s' event", event)

    def reset(self) -> None:
        r"""Reset the event manager.

        This method removes all registered event handlers from the
        event manager and resets the last triggered event to ``None``.
        After calling this method, the event manager returns to its
        initial state.

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
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            True
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.last_triggered_event
            'my_event'
            >>> # Reset the event manager
            >>> manager.reset()
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            False
            >>> manager.last_triggered_event is None
            True

            ```
        """
        with self._lock:
            for subs in self._subscriptions.values():
                for sub in subs:
                    sub._active = False
            self._subscriptions.clear()
            self._last_triggered_event = None
