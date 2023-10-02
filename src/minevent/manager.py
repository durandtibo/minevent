r"""This module implements an event manager."""

from __future__ import annotations

__all__ = ["EventManager"]

import logging
from collections import defaultdict

from coola.utils import str_indent, str_mapping, str_sequence

from minevent.handlers import BaseEventHandler

logger = logging.getLogger(__name__)


class EventManager:
    r"""Implements an event manager.

    This event manager allows adding event handlers and firing events.
    An event is represented by a case-sensitive string.

    Example usage:

    .. code-block:: pycon

        >>> from minevent import EventHandler, EventManager
        >>> def hello_handler():
        ...     print("Hello!")
        ...
        >>> manager = EventManager()
        >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
        >>> manager.trigger_event("my_event")
        Hello!
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
        r"""Gets the last event name that was triggered.

        Returns
        -------
            str or ``None``: The last event name that was fired or
                ``None`` if no event was fired.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.last_triggered_event
        """
        return self._last_triggered_event

    def add_event_handler(self, event: str, event_handler: BaseEventHandler) -> None:
        r"""Adds an event handler to an event.

        The event handler will be called everytime the event happens.

        Args:
        ----
            event (str): Specifies the event to attach the event
                handler.
            event_handler (``BaseEventHandler``): Specifies the
                event handler to attach to the event.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventManager, EventHandler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager = EventManager()
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
        """
        self._event_handlers[str(event)].append(event_handler)
        logger.debug(f"Added {event_handler} to event {event}")

    def trigger_event(self, event: str) -> None:
        r"""Triggers the handler(s) for the given event.

        Args:
        ----
            event (str): Specifies the event to fire.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventHandler, EventManager
            >>> manager = EventManager()
            >>> manager.trigger_event("my_event")  # do nothing because there is no event handler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager.add_event_handler("my_event", EventHandler(hello_handler))
            >>> manager.trigger_event("my_event")
            Hello!
        """
        logger.debug(f"Firing {event} event")
        self._last_triggered_event = event
        for event_handler in self._event_handlers[event]:
            event_handler.handle()

    def has_event_handler(self, event_handler: BaseEventHandler, event: str | None = None) -> bool:
        r"""Indicates if a handler is registered in the event manager.

        Note that this method relies on the ``equal`` method of the
        input event handler to compare event handlers.

        Args:
        ----
            event_handler (``BaseEventHandler``): Specifies the eventn
                handler to check.
            event (str or ``None``): Specifies an event to check. If
                the value is ``None``, it will check all the events.
                Default: ``None``

        Example usage:

        .. code-block:: pycon

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
        """
        events = [event] if event else self._event_handlers
        for evnt in events:
            for handler in self._event_handlers[evnt]:
                if event_handler.equal(handler):
                    return True
        return False

    def remove_event_handler(self, event: str, event_handler: BaseEventHandler) -> None:
        r"""Removes an event handler of a given event.

        Note that if the same event handler was added multiple times
        the event, all the duplicated handlers are removed. This
        method relies on the ``equal`` method of the input event
        handler to compare event handlers.

        Args:
        ----
            event (str): Specifies the event handler is attached to.
            event_handler (``BaseEventHandler``): Specifies the event
                handler to remove.

        Raises:
        ------
            ValueError: if the event does not exist or if the handler
                is not attached to the event.

        Example usage:

        .. code-block:: pycon

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
        """
        if event not in self._event_handlers:
            raise RuntimeError(f"'{event}' event does not exist")

        new_event_handlers = [
            handler for handler in self._event_handlers[event] if not event_handler.equal(handler)
        ]
        if len(new_event_handlers) == len(self._event_handlers[event]):
            raise RuntimeError(
                f"{event_handler} is not found among registered event handlers for '{event}' event"
            )
        if len(new_event_handlers) > 0:
            self._event_handlers[event] = new_event_handlers
        else:
            del self._event_handlers[event]
        logger.debug(f"Removed {event_handler} in '{event}' event")

    def reset(self) -> None:
        r"""Resets the event manager.

        This method removes all the event handlers from the event manager.

        Example usage:

        .. code-block:: pycon

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
        """
        self._event_handlers.clear()
        self._last_triggered_event = None
