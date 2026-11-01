r"""Implement the subscription returned when an event handler is
added."""

from __future__ import annotations

__all__ = ["Subscription"]

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

    from minevent.handlers import BaseEventHandler
    from minevent.manager import EventManager


class Subscription:
    r"""Represent the registration of an event handler to an event.

    A subscription is returned by ``EventManager.add_event_handler``.
    It is the registration itself: the manager stores it, and it
    removes exactly the registration that created it. The handler does
    not need to be re-created to be unsubscribed, other equal handlers
    are not removed, and registering the same handler twice creates two
    independent subscriptions.

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
        self._active = True

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
                ``remove_event_handler``, ``clear_event``, ``reset``
                or because it was a ``once`` handler that ran).
        """
        return self._active

    def remove(self) -> bool:
        r"""Remove the registration.

        Only this registration is removed, even if equal handlers are
        registered to the same event. Calling this method again, or
        after the handler was removed by another way, does nothing.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.
        """
        return self._manager._remove(self)
