r"""Implement the event manager."""

from __future__ import annotations

__all__ = ["EventManager"]

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from coola.utils.format import str_indent, str_mapping, str_sequence

if TYPE_CHECKING:
    from minevent.handlers import BaseEventHandler

logger: logging.Logger = logging.getLogger(__name__)


class EventManager:
    r"""Implement an event manager.

    This event manager allows registering event handlers and triggering
    events. An event is represented by a case-sensitive string. Each
    event can have multiple handlers attached, and all handlers are
    executed in the order they were added when the event is triggered.
    The manager also tracks the last triggered event.

    Example:
        ```pycon
        >>> from minevent import EventHandler, EventManager
        >>> def hello_handler():
        ...     print("Hello!")
        ...
        >>> manager = EventManager()
        >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
        >>> manager.trigger_event("my_event")
        Hello!

        ```
    """

    def __init__(self) -> None:
        # This variable is used to store the handlers associated to each event.
        self._event_handlers = defaultdict(list)
        # This variable is used to track the last fired event name
        self._last_triggered_event = None
        self.reset()

    def __repr__(self) -> str:
        event_handlers = str_mapping(
            {
                event: "\n" + str_sequence(handler) if handler else ""
                for event, handler in self._event_handlers.items()
            }
        )
        args = str_indent(
            str_mapping(
                {
                    "event_handlers": "\n" + event_handlers if event_handlers else event_handlers,
                    "last_triggered_event": self._last_triggered_event,
                }
            )
        )
        return f"{self.__class__.__qualname__}(\n  {args}\n)"

    @property
    def last_triggered_event(self) -> str | None:
        r"""Get the last event name that was triggered.

        Returns:
            The last event name that was fired of ``None`` if no event
                was fired.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.last_triggered_event

            ```
        """
        return self._last_triggered_event

    def add_event_handler(self, event: str, event_handler: BaseEventHandler) -> None:
        r"""Add an event handler to an event.

        The event handler will be called every time the specified event
        is triggered. Multiple handlers can be registered to the same
        event, and they will be executed in the order they were added.

        Args:
            event: The event name (case-sensitive string) to which the
                event handler should be attached.
            event_handler: The event handler instance to attach to the
                event.

        Example:
            ```pycon
            >>> from minevent import EventManager, EventHandler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager = EventManager()
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))

            ```
        """
        self._event_handlers[str(event)].append(event_handler)
        logger.debug(f"Added {event_handler} to event {event}")

    def trigger_event(self, event: str) -> None:
        r"""Trigger the handler(s) for the given event.

        This method executes all event handlers registered for the
        specified event in the order they were added. The last
        triggered event name is updated regardless of whether any
        handlers are registered.

        Args:
            event: The event name (case-sensitive string) to trigger.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.trigger_event("my_event")  # do nothing because there is no event handler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!

            ```
        """
        logger.debug(f"Firing {event} event")
        self._last_triggered_event = event
        for event_handler in self._event_handlers[event]:
            event_handler.handle()

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
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
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
        events = [event] if event else self._event_handlers
        for evnt in events:
            for handler in self._event_handlers[evnt]:
                if event_handler.equal(handler):
                    return True
        return False

    def remove_event_handler(self, event: str, event_handler: BaseEventHandler) -> None:
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

        Raises:
            RuntimeError: if the event does not exist or if the
                handler is not attached to the event.

        Example:
            ```pycon
            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            True
            >>> # Remove the event handler of the engine
            >>> manager.remove_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            False

            ```
        """
        if event not in self._event_handlers:
            msg = f"'{event}' event does not exist"
            raise RuntimeError(msg)

        new_event_handlers = [
            handler for handler in self._event_handlers[event] if not event_handler.equal(handler)
        ]
        if len(new_event_handlers) == len(self._event_handlers[event]):
            msg = (
                f"{event_handler} is not found among registered event handlers for '{event}' event"
            )
            raise RuntimeError(msg)
        if len(new_event_handlers) > 0:
            self._event_handlers[event] = new_event_handlers
        else:
            del self._event_handlers[event]
        logger.debug(f"Removed {event_handler} in '{event}' event")

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
            >>> # Add an event handler to the engine
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> from minevent import EventHandler
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            True
            >>> manager.trigger_event("my_event")
            >>> manager.last_triggered_event
            my_event
            >>> # Reset the event manager
            >>> manager.reset()
            >>> # Check if `hello_handler` is registered in the event manager for 'my_event' event
            >>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
            False
            >>> manager.last_triggered_event
            None

            ```
        """
        self._event_handlers.clear()
        self._last_triggered_event = None
