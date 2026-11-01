r"""Implement the event manager."""

from __future__ import annotations

__all__ = ["EventManager"]

import logging
import threading
from typing import Any

from coola.utils.format import str_indent, str_mapping, str_sequence

from minevent.handlers import BaseEventHandler
from minevent.subscription import Subscription

logger: logging.Logger = logging.getLogger(__name__)


def _check_event(event: object) -> None:
    r"""Check that an event name is a string.

    Raises:
        TypeError: if ``event`` is not a ``str``.
    """
    if not isinstance(event, str):
        msg = f"event must be a str, but got {type(event).__qualname__}"
        raise TypeError(msg)


class _OnceEventHandler(BaseEventHandler):
    r"""Wrap an event handler to run it only on the next trigger.

    The wrapper removes its own registration before calling the
    wrapped handler, so the handler runs once even if it triggers the
    same event again or raises.

    Args:
        event_handler: The wrapped event handler.
    """

    def __init__(self, event_handler: BaseEventHandler) -> None:
        self.event_handler = event_handler
        self.subscription: Subscription | None = None

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.event_handler!r})"

    def equal(self, other: Any) -> bool:
        if isinstance(other, _OnceEventHandler):
            other = other.event_handler
        return self.event_handler.equal(other)

    def handle(self, **payload: Any) -> None:
        if self.subscription is not None:
            self.subscription.remove()
        self.event_handler.handle(**payload)


def _unwrap(event_handler: BaseEventHandler) -> BaseEventHandler:
    r"""Return the user event handler of a registered event handler.

    Args:
        event_handler: A registered event handler.

    Returns:
        The wrapped event handler if ``event_handler`` is a one-time
            wrapper, otherwise ``event_handler``.
    """
    if isinstance(event_handler, _OnceEventHandler):
        return event_handler.event_handler
    return event_handler


class EventManager:
    r"""Implement an event manager.

    This event manager allows registering event handlers and triggering
    events. An event is represented by a case-sensitive string. Each
    event can have multiple handlers attached, and all handlers are
    executed in the order they were added when the event is triggered.
    The manager also tracks the last triggered event.

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
        # This variable is used to store the handlers associated to each event.
        self._event_handlers: dict[str, list[BaseEventHandler]] = {}
        # This variable is used to track the last fired event name
        self._last_triggered_event: str | None = None
        # This lock protects the state above. It is reentrant, so a handler can use the manager.
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        with self._lock:
            config = {
                "event_handlers": self._format_event_handlers(),
                "last_triggered_event": self._last_triggered_event,
            }
        args = str_indent(str_mapping(config))
        return f"{self.__class__.__qualname__}(\n  {args}\n)"

    def _format_event_handlers(self) -> str:
        r"""Format the registered handlers, one block per event.

        Returns:
            The formatted handlers, starting with a newline, or an
                empty string if no handler is registered.
        """
        if not self._event_handlers:
            return ""
        return "\n" + str_mapping(
            {
                event: "\n" + str_sequence(handlers)
                for event, handlers in self._event_handlers.items()
            }
        )

    def __contains__(self, event: object) -> bool:
        with self._lock:
            return event in self._event_handlers

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
            return list(self._event_handlers)

    @property
    def last_triggered_event(self) -> str | None:
        r"""Get the last event name that was triggered.

        The name is recorded when the dispatch starts, before any
        handler runs. It is therefore already updated when a handler
        reads it, and it is kept even if a handler raises.

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
                until then. Default is ``False``.

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
        registered = event_handler
        if once:
            registered = _OnceEventHandler(event_handler)
        with self._lock:
            self._event_handlers.setdefault(event, []).append(registered)
        subscription = Subscription(event, registered, self._remove_registration)
        if isinstance(registered, _OnceEventHandler):
            registered.subscription = subscription
        logger.debug("Added %s to event %s", event_handler, event)
        return subscription

    def _remove_registration(self, event: str, event_handler: BaseEventHandler) -> bool:
        r"""Remove one registered event handler, compared by identity.

        Args:
            event: The event name.
            event_handler: The registered event handler instance.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                is not registered.
        """
        with self._lock:
            handlers = self._event_handlers.get(event, [])
            for i, handler in enumerate(handlers):
                if handler is event_handler:
                    del handlers[i]
                    if not handlers:
                        del self._event_handlers[event]
                    logger.debug("Removed %s in '%s' event", event_handler, event)
                    return True
            return False

    def trigger_event(self, event: str, **payload: Any) -> None:
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

        The keyword arguments ``payload`` are passed to every
        handler as keyword arguments, after the arguments given at
        registration. Without payload, handlers are called exactly as
        before. A handler that does not accept the payload raises a
        ``TypeError``.

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
        _check_event(event)
        logger.debug("Firing %s event", event)
        with self._lock:
            self._last_triggered_event = event
            event_handlers = tuple(self._event_handlers.get(event, ()))
        for event_handler in event_handlers:
            event_handler.handle(**payload)

    def has_event_handler(self, event_handler: BaseEventHandler, event: str | None = None) -> bool:
        r"""Indicate if a handler is registered in the event manager.

        This method checks whether a specific event handler is
        registered, either for a specific event or across all events.
        Note that this method relies on the ``equal`` method of the
        input event handler to compare event handlers.

        Args:
            event_handler: The event handler instance to search for in
                the registered handlers.
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
        with self._lock:
            events = list(self._event_handlers) if event is None else [event]
            registered = [tuple(self._event_handlers.get(evnt, ())) for evnt in events]
        return any(
            event_handler.equal(_unwrap(handler)) for handlers in registered for handler in handlers
        )

    def remove_event_handler(
        self, event: str, event_handler: BaseEventHandler, *, missing_ok: bool = False
    ) -> None:
        r"""Remove an event handler of a given event.

        This method removes all occurrences of the specified event
        handler from the given event. If the same event handler was
        added multiple times to the event, all duplicates are removed.
        This method relies on the ``equal`` method of the input event
        handler to compare event handlers.

        Args:
            event: The event name (case-sensitive string) from which
                the handler should be removed.
            event_handler: The event handler instance to remove from
                the event.
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
        with self._lock:
            if event not in self._event_handlers:
                if missing_ok:
                    return
                msg = f"'{event}' event does not exist"
                raise ValueError(msg)

            new_event_handlers = [
                handler
                for handler in self._event_handlers[event]
                if not event_handler.equal(_unwrap(handler))
            ]
            if len(new_event_handlers) == len(self._event_handlers[event]):
                if missing_ok:
                    return
                msg = f"{event_handler} is not found among registered event handlers for '{event}' event"
                raise ValueError(msg)
            if len(new_event_handlers) > 0:
                self._event_handlers[event] = new_event_handlers
            else:
                del self._event_handlers[event]
        logger.debug("Removed %s in '%s' event", event_handler, event)

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
            removed = self._event_handlers.pop(event, None)
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
            self._event_handlers.clear()
            self._last_triggered_event = None
