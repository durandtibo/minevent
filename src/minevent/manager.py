r"""Implement the event manager."""

from __future__ import annotations

__all__ = ["EventManager", "Subscription"]

import functools
import threading
from collections.abc import Awaitable, Coroutine
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType
    from typing import NoReturn, Self, TypeVar

    from minevent.conditions import Condition

    _F = TypeVar("_F", bound=Callable[..., object])


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


def _accepted_keywords(func: Callable[..., object]) -> frozenset[str] | None:
    r"""Get the keyword arguments that a callable accepts.

    Args:
        func: The callable to inspect.

    Returns:
        The names of the parameters that can be passed by keyword,
            or ``None`` if the callable accepts any keyword (it has a
            ``**kwargs`` parameter) or if its signature cannot be
            inspected. The signature of a ``functools.partial`` does
            not contain the positional arguments that it binds.

    Example:
        ```pycon
        >>> from minevent.manager import _accepted_keywords
        >>> def func(a, /, b, *, c, **kwargs): ...
        >>> _accepted_keywords(func) is None
        True
        >>> def func(a, /, b, *, c): ...
        >>> sorted(_accepted_keywords(func))
        ['b', 'c']

        ```
    """
    import inspect  # noqa: PLC0415

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


def _check_not_awaitable(result: object, handler: Callable[..., object]) -> None:
    r"""Check that a handler did not return an awaitable.

    A coroutine is closed, so it does not emit a ``RuntimeWarning``
    because it was never awaited.

    Args:
        result: The value returned by the handler.
        handler: The handler that returned ``result``. The error
            names its function, never its arguments.

    Raises:
        TypeError: if ``result`` is an awaitable.
    """
    if result is not None and isinstance(result, Awaitable):
        if isinstance(result, Coroutine):
            result.close()
        msg = f"{_describe(handler)} returned an awaitable; use atrigger_event"
        raise TypeError(msg)


def _describe(handler: Callable[..., object]) -> str:
    r"""Name a handler without calling the ``repr`` of its data.

    The ``repr`` of a handler can contain its arguments, which can be
    large or raise, so it is not used in the note of an exception.

    Args:
        handler: The callable to name.

    Returns:
        The qualified name of the function under a
            ``functools.partial`` (nested partials are unwrapped), or
            the qualified name of the class of the handler if it has
            no name (for example a callable object).

    Example:
        ```pycon
        >>> import functools
        >>> from minevent.manager import _describe
        >>> _describe(print)
        'print'
        >>> _describe(functools.partial(print, "Hello!"))
        'print'

        ```
    """
    while isinstance(handler, functools.partial):
        handler = handler.func
    return getattr(handler, "__qualname__", type(handler).__qualname__)


def _add_error_note(exc: Exception, event: str, handler: Callable[..., object]) -> None:
    r"""Add a note to the exception raised by an event handler.

    The note names the event and the function of the handler, never
    its arguments. The note is not added if the exception already has
    it, so an exception instance that is raised again (or a handler
    that triggers its own event) has one note per distinct pair of
    event and handler.

    Args:
        exc: The exception raised by the event handler.
        event: The event that was triggered.
        handler: The handler that raised the exception.
    """
    note = f"raised by {_describe(handler)} while handling the event {event!r}"
    if note not in getattr(exc, "__notes__", ()):
        exc.add_note(note)


class Subscription:
    r"""Represent the registration of a handler to an event.

    A subscription is returned by ``EventManager.add_event_handler``.
    It is the registration itself: the manager stores it with the
    options of the registration, and it removes exactly the
    registration that created it. The handler does
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
        handler: The registered handler: any callable.
        once: If ``True``, the registration is removed just before
            its first execution.
        condition: The condition evaluated before the handler, or
            ``None`` if the handler always runs.
        filter_payload: If ``True``, only the payload keys that the
            handler accepts are passed to it.

    Example:
        ```pycon
        >>> from minevent import EventManager
        >>> manager = EventManager()
        >>> subscription = manager.add_event_handler("my_event", print)
        >>> subscription.event
        'my_event'
        >>> subscription.handler is print
        True
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
        >>> with manager.add_event_handler("my_event", print):
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
        handler: Callable[..., object],
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> None:
        self._manager = manager
        self._event = event
        self._handler = handler
        self._once = once
        self._condition = condition
        self._filter_payload = filter_payload
        # The accepted keys are computed once, at registration.
        self._payload_keys = _accepted_keywords(handler) if filter_payload else None

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
            f"(event={self._event!r}, handler={_describe(self._handler)!r})"
        )

    @property
    def event(self) -> str:
        r"""Get the event name of the registration.

        Returns:
            The event name.
        """
        return self._event

    @property
    def handler(self) -> Callable[..., object]:
        r"""Get the registered handler.

        Returns:
            The handler given to ``add_event_handler``.
        """
        return self._handler

    @property
    def once(self) -> bool:
        r"""Indicate if the registration is removed just before its
        first execution.

        Returns:
            ``True`` if the event handler runs at most once, otherwise
                ``False``.
        """
        return self._once

    @property
    def condition(self) -> Condition | None:
        r"""Get the condition evaluated before the handler.

        Returns:
            The condition, or ``None`` if the handler always runs.
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

    def _call(self, payload: dict[str, object]) -> object:
        r"""Run the registration: condition, once claim, payload filter
        and handler.

        The condition decides whether the handler would run, and the
        claim of a ``once`` registration decides who runs it: the
        registration is removed by an atomic claim just before its
        handler, so it runs at most once whatever the number of
        threads. A condition that is ``False`` (or that raises) does
        not consume a ``once`` registration.

        Args:
            payload: The payload given to ``trigger_event`` or
                ``atrigger_event``.

        Returns:
            The value returned by the handler, or ``None`` if the
                condition is ``False`` or if the registration lost the
                claim (it was already removed). It is awaitable if the
                handler is a coroutine function.
        """
        if self._condition is not None and not self._condition():
            return None
        if self._once and not self.remove():
            return None
        if self._payload_keys is not None:
            payload = {key: value for key, value in payload.items() if key in self._payload_keys}
        return self._handler(**payload)

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
    needed. Nothing is logged: to trace the registrations, read
    ``get_subscriptions(event)``, or wrap the handler.

    A handler is any callable, called as ``handler(**payload)``. The
    options of a registration (``once``, ``condition`` and
    ``filter_payload``) are the keyword-only arguments of
    ``add_event_handler`` and ``on``. Use ``functools.partial`` to bind
    other arguments.

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
        >>> from minevent import EventManager
        >>> def hello_handler():
        ...     print("Hello!")
        ...
        >>> manager = EventManager()
        >>> bool(manager)
        True
        >>> _ = manager.add_event_handler("my_event", hello_handler)
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
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.events
            []
            >>> _ = manager.add_event_handler("my_event", print)
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
            >>> handler = print
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
        handler: Callable[..., object],
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> Subscription:
        r"""Add a handler to an event.

        The handler will be called every time the specified event is
        triggered, as ``handler(**payload)``. Multiple handlers can be
        registered to the same event, and they will be executed in the
        order they were added. Use ``functools.partial`` to bind
        other arguments.

        Args:
            event: The event name (case-sensitive string) to which
                the handler should be attached.
            handler: The callable to attach to the event.
            once: If ``True``, the handler is removed just before its
                first execution, so it runs at most once (P9 of the
                architecture page). A condition that is ``False`` does
                not consume the registration: it waits for the first
                time the condition is ``True``. Default is ``False``.
            condition: An optional condition: a function without
                argument that returns a boolean. It is called each
                time the event is triggered, before the handler, and
                the handler runs only if it returns ``True``. If
                ``None``, the handler always runs. Default is
                ``None``.
            filter_payload: If ``True``, only the payload keys that
                the signature of the handler accepts are passed to
                it, so handlers with different needs can share an
                event without ``**kwargs``. The accepted keys are
                computed once, at registration. A handler with a
                ``**kwargs`` parameter, or whose signature cannot be
                inspected, receives the whole payload. The signature
                of a ``functools.partial`` does not contain the
                positional arguments that it binds. Default is
                ``False``.

        Returns:
            A subscription whose ``remove`` method removes this
                registration only.

        Raises:
            TypeError: if ``event`` is not a string, if ``handler``
                is not callable, or if ``condition`` is neither
                ``None`` nor callable. The manager is unchanged.

        Example:
            ```pycon
            >>> import functools
            >>> from minevent import EventManager, PeriodicCondition
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> manager = EventManager()
            >>> subscription = manager.add_event_handler("my_event", hello_handler)
            >>> manager.trigger_event("my_event")
            Hello!
            >>> subscription.remove()
            True
            >>> manager.trigger_event("my_event")
            >>> _ = manager.add_event_handler("my_event", hello_handler, once=True)
            >>> manager.trigger_event("my_event")
            Hello!
            >>> manager.trigger_event("my_event")
            >>> _ = manager.add_event_handler("greet", functools.partial(print, "Hello!"))
            >>> manager.trigger_event("greet")
            Hello!
            >>> _ = manager.add_event_handler(
            ...     "tick", hello_handler, condition=PeriodicCondition(freq=2)
            ... )
            >>> manager.trigger_event("tick")
            Hello!
            >>> manager.trigger_event("tick")
            >>> def epoch_handler(epoch):
            ...     print(f"epoch {epoch}")
            ...
            >>> _ = manager.add_event_handler("epoch_end", epoch_handler, filter_payload=True)
            >>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
            epoch 3

            ```
        """
        _check_event(event)
        if not callable(handler):
            msg = f"handler must be callable, but got {handler!r}"
            raise TypeError(msg)
        if condition is not None and not callable(condition):
            msg = f"condition must be callable, but got {condition!r}"
            raise TypeError(msg)
        subscription = Subscription(
            self, event, handler, once=once, condition=condition, filter_payload=filter_payload
        )
        with self._lock:
            self._subscriptions.setdefault(event, {})[subscription] = None
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

        The decorated function is registered with
        ``add_event_handler(event, func, once=once, condition=condition,
        filter_payload=filter_payload)`` and returned unchanged. Use
        ``add_event_handler`` if you need the ``Subscription``.

        Args:
            event: The event name (case-sensitive string).
            once: If ``True``, the handler runs at most once. See
                ``add_event_handler``. Default is ``False``.
            condition: An optional condition evaluated before the
                handler. See ``add_event_handler``. Default is ``None``.
            filter_payload: If ``True``, only the payload keys that
                the function accepts are passed to it. See
                ``add_event_handler``. Default is ``False``.

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
            self.add_event_handler(
                event, func, once=once, condition=condition, filter_payload=filter_payload
            )
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
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> manager.trigger_event("my_event")  # do nothing because there is no event handler
            >>> def hello_handler():
            ...     print("Hello!")
            ...
            >>> _ = manager.add_event_handler("my_event", hello_handler)
            >>> manager.trigger_event("my_event")
            Hello!
            >>> def epoch_handler(epoch):
            ...     print(f"epoch {epoch}")
            ...
            >>> _ = manager.add_event_handler("epoch_end", epoch_handler)
            >>> manager.trigger_event("epoch_end", epoch=3)
            epoch 3

            ```
        """
        subscriptions = self.get_subscriptions(event)
        for subscription in subscriptions:
            try:
                _check_not_awaitable(subscription._call(payload), subscription.handler)
            except Exception as exc:
                _add_error_note(exc, event, subscription.handler)
                raise

    async def atrigger_event(self, event: str, /, **payload: object) -> None:
        r"""Trigger the handler(s) for the given event, awaiting the
        coroutine handlers.

        This method behaves like ``trigger_event``, but the handlers
        that are coroutine functions (or return an awaitable) are
        awaited.
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
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> async def hello_handler(name):
            ...     print(f"Hello {name}!")
            ...
            >>> _ = manager.add_event_handler("my_event", hello_handler)
            >>> asyncio.run(manager.atrigger_event("my_event", name="John"))
            Hello John!

            ```
        """
        subscriptions = self.get_subscriptions(event)
        for subscription in subscriptions:
            try:
                result = subscription._call(payload)
                if result is not None and isinstance(result, Awaitable):
                    await result
            except Exception as exc:
                _add_error_note(exc, event, subscription.handler)
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
            >>> from minevent import EventManager
            >>> manager = EventManager()
            >>> _ = manager.add_event_handler("my_event", print)
            >>> manager.clear_event("my_event")
            >>> manager.events
            []

            ```
        """
        _check_event(event)
        with self._lock:
            self._subscriptions.pop(event, None)

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
            >>> _ = manager.add_event_handler("my_event", hello_handler)
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
