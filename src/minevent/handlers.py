r"""Implement the event handlers."""

from __future__ import annotations

__all__ = ["BaseEventHandler", "ConditionalEventHandler", "EventHandler"]

import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from coola.equality import objects_are_equal
from coola.utils.format import str_indent, str_mapping

from minevent.conditions import as_condition

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from minevent.conditions import BaseCondition


class BaseEventHandler(ABC):  # noqa: PLW1641
    r"""Define the base class to implement an event handler.

    A child class has to implement the following methods:

        - ``handle``
        - ``equal``

    ``equal`` is the primary comparison API and ``==`` delegates to
    it. Because equality is defined by ``equal`` (for example with
    ``coola.objects_are_equal``, which supports arrays and tensors),
    no consistent hash can be computed, so event handlers are
    intentionally unhashable: they cannot be put in a ``set`` or used
    as ``dict`` keys. Use the ``Subscription`` returned by
    ``EventManager.add_event_handler`` to identify a registration.

    Example:
        ```pycon
        >>> from minevent import EventHandler
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> handler = EventHandler(hello_handler)
        >>> handler
        EventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
        >>> handler.handle()
        Hello!

        ```
    """

    def __eq__(self, other: object) -> bool:
        return self.equal(other)

    @abstractmethod
    def equal(self, other: Any) -> bool:
        r"""Compare two event handlers for equality.

        This method should be implemented by child classes to define
        how event handlers are compared. This is used by the event
        manager to check for duplicate handlers.

        Args:
            other: The other object to compare with. Can be any type,
                though typically an event handler.

        Returns:
            ``True`` if the two event handlers are considered equal,
                otherwise ``False``.

        Example:
            ```pycon
            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> handler = EventHandler(hello_handler)
            >>> handler.equal(EventHandler(hello_handler))
            True
            >>> handler.equal(EventHandler(print, handler_args=["Hello!"]))
            False

            ```
        """

    @abstractmethod
    def handle(self, **payload: Any) -> None:
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
    ``payload`` is the data given when the event is triggered. Two
    event handlers are equal if they have the same class, handler,
    arguments and condition.

    Equality compares the handlers with ``coola.objects_are_equal``,
    which falls back to ``==`` for functions. Module-level functions
    compare equal to themselves, but lambdas and bound methods of
    different instances (``obj.method != other.method``) do not, so
    ``has_event_handler`` and ``remove_event_handler`` do not find a
    handler built from a new lambda or from another instance. Keep a
    reference to the function, or use the ``Subscription`` returned
    by ``EventManager.add_event_handler``, which does not need
    equality. Arrays and tensors in ``handler_args`` are compared by
    value.

    Args:
        handler: The callable function or method to be invoked when
            the event is triggered (and the condition is ``True``).
        handler_args: The positional arguments to pass to the handler
            when it is called. Default is ``None``.
        handler_kwargs: The keyword arguments to pass to the handler
            when it is called. The dictionary is copied, so changing
            it afterwards does not change the handler.
            Default is ``None``.
        condition: The condition object that controls whether the
            handler is executed. The condition's ``evaluate`` method
            is called without arguments, each time the event is
            triggered, and must return a boolean value. A function
            without argument that returns a boolean is also accepted;
            it is wrapped in a ``CallableCondition``. If ``None``,
            the handler is always executed. Default is ``None``.

    Raises:
        TypeError: if ``handler`` is not callable, or if
            ``condition`` is neither ``None``, a ``BaseCondition``
            nor callable.

    Example:
        ```pycon
        >>> from minevent import EventHandler, PeriodicCondition
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> handler = EventHandler(hello_handler)
        >>> handler
        EventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
        >>> handler.handle()
        Hello!
        >>> handler = EventHandler(print, handler_args=["Hello!"])
        >>> handler.handle()
        Hello!
        >>> handler = EventHandler(hello_handler, condition=PeriodicCondition(freq=3))
        >>> handler
        EventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
          (condition): PeriodicCondition(freq=3, skip_first=False, step=0)
        )
        >>> handler.handle()
        Hello!
        >>> handler.handle()
        >>> handler.handle()
        >>> handler.handle()
        Hello!

        ```
    """

    def __init__(
        self,
        handler: Callable,
        handler_args: Sequence[Any] | None = None,
        handler_kwargs: dict[str, Any] | None = None,
        *,
        condition: BaseCondition | Callable[[], bool] | None = None,
    ) -> None:
        if not callable(handler):
            msg = f"handler is not callable: {handler}"
            raise TypeError(msg)
        self._handler = handler
        self._handler_args = tuple(handler_args or ())
        self._handler_kwargs = dict(handler_kwargs or {})
        self._condition = None if condition is None else as_condition(condition)

    def __repr__(self) -> str:
        config = {
            "handler": self._handler,
            "handler_args": self._handler_args,
            "handler_kwargs": self._handler_kwargs,
        }
        if self._condition is not None:
            config["condition"] = self._condition
        args = str_indent(str_mapping(config))
        return f"{self.__class__.__qualname__}(\n  {args}\n)"

    @property
    def handler(self) -> Callable:
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
    def condition(self) -> BaseCondition | None:
        r"""Get the condition that controls handler execution.

        Returns:
            The condition that must evaluate to ``True`` for the
                handler to be executed, or ``None`` if the handler is
                always executed.
        """
        return self._condition

    def _key(self) -> tuple[Any, ...]:
        r"""Return the values compared by ``equal``.

        Returns:
            The handler, the arguments and the condition.
        """
        return (self._handler, self._handler_args, self._handler_kwargs, self._condition)

    def equal(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return objects_are_equal(self._key(), other._key())

    def handle(self, **payload: Any) -> None:
        if self._condition is None or self._condition.evaluate():
            self._handler(*self._handler_args, **self._handler_kwargs, **payload)


def ConditionalEventHandler(  # noqa: N802
    handler: Callable,
    condition: BaseCondition,
    handler_args: Sequence[Any] | None = None,
    handler_kwargs: dict[str, Any] | None = None,
) -> EventHandler:
    r"""Create an event handler that is executed only if a condition is
    ``True``.

    This function is deprecated and will be removed in a future
    release. Use ``EventHandler(handler, condition=condition)``
    instead.

    Args:
        handler: The callable function or method to be invoked when
            the event is triggered and the condition is ``True``.
        condition: The condition object that controls whether the
            handler is executed.
        handler_args: The positional arguments to pass to the handler
            when it is called. Default is ``None``.
        handler_kwargs: The keyword arguments to pass to the handler
            when it is called. Default is ``None``.

    Returns:
        An ``EventHandler`` with the given condition.

    Raises:
        TypeError: if ``handler`` is not callable.

    Example:
        ```pycon
        >>> import warnings
        >>> from minevent import ConditionalEventHandler, PeriodicCondition
        >>> with warnings.catch_warnings():
        ...     warnings.simplefilter("ignore", DeprecationWarning)
        ...     handler = ConditionalEventHandler(print, PeriodicCondition(freq=3))
        ...
        >>> type(handler).__name__
        'EventHandler'

        ```
    """
    warnings.warn(
        "ConditionalEventHandler is deprecated and will be removed in a future release. "
        "Use EventHandler(handler, condition=condition) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return EventHandler(
        handler, handler_args=handler_args, handler_kwargs=handler_kwargs, condition=condition
    )
