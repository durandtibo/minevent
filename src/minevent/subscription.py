r"""Implement the subscription returned when an event handler is
added."""

from __future__ import annotations

__all__ = ["Subscription"]

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from minevent.handlers import BaseEventHandler


class Subscription:
    r"""Represent the registration of an event handler to an event.

    A subscription is returned by ``EventManager.add_event_handler``.
    It removes exactly the registration that created it, so the
    handler does not need to be re-created to be unsubscribed, and
    other equal handlers are not removed.

    A subscription is a context manager: the registration is removed
    when the ``with`` block exits.

    Args:
        event: The event name of the registration.
        event_handler: The registered event handler.
        remove_func: The function that removes the registration. It
            takes the event name and the event handler, and returns
            ``True`` if the registration was removed, ``False`` if it
            was already removed.
        is_active_func: The function that indicates if the
            registration is still registered. It takes the event name
            and the event handler. If ``None``, the subscription is
            active until ``remove`` is called. Default is ``None``.

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
        event: str,
        event_handler: BaseEventHandler,
        remove_func: Callable[[str, BaseEventHandler], bool],
        *,
        is_active_func: Callable[[str, BaseEventHandler], bool] | None = None,
    ) -> None:
        self._event = event
        self._event_handler = event_handler
        self._remove_func = remove_func
        self._is_active_func = is_active_func
        self._removed = False

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
    def active(self) -> bool:
        r"""Indicate if the registration is still registered.

        Returns:
            ``True`` if the event handler is still registered,
                ``False`` if it was removed (by this subscription, by
                ``remove_event_handler``, ``clear_event``, ``reset``
                or because it was a ``once`` handler that ran).
        """
        if self._is_active_func is None:
            return not self._removed
        return self._is_active_func(self._event, self._event_handler)

    def remove(self) -> bool:
        r"""Remove the registration.

        Only this registration is removed, even if equal handlers are
        registered to the same event. Calling this method again, or
        after the handler was removed by another way, does nothing.

        Returns:
            ``True`` if the registration was removed, ``False`` if it
                was already removed.
        """
        self._removed = True
        return self._remove_func(self._event, self._event_handler)
