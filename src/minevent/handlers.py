r"""Implement the event handlers."""

from __future__ import annotations

__all__ = [
    "BaseEventHandler",
    "BaseEventHandlerWithArguments",
    "ConditionalEventHandler",
    "EventHandler",
]

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from coola.equality import objects_are_equal
from coola.utils.format import str_indent, str_mapping

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from minevent.conditions import BaseCondition


class BaseEventHandler(ABC):  # noqa: PLW1641
    r"""Define the base class to implement an event handler.

    A child class has to implement the following methods:

        - ``handle``
        - ``equal``

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
    def handle(self) -> None:
        r"""Handle the event.

        This method executes the logic associated with the event
        handler. It should be implemented by child classes to define
        the specific behavior when an event is triggered.

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


class BaseEventHandlerWithArguments(BaseEventHandler):
    r"""Define a base class to implement an event handler with positional
    and/or keyword arguments.

    A child class has to implement the ``equal`` method.

    Args:
        handler: The callable function or method to be invoked when
            the event is triggered.
        handler_args: The positional arguments to pass to the handler
            when it is called. Default is ``None``.
        handler_kwargs: The keyword arguments to pass to the handler
            when it is called. Default is ``None``.

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
        >>> handler = EventHandler(print, handler_args=["Hello!"])
        >>> handler.handle()
        Hello!

        ```
    """

    def __init__(
        self,
        handler: Callable,
        handler_args: Sequence[Any] | None = None,
        handler_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not callable(handler):
            msg = f"handler is not callable: {handler}"
            raise TypeError(msg)
        self._handler = handler
        self._handler_args = tuple(handler_args or ())
        self._handler_kwargs = handler_kwargs or {}

    def __repr__(self) -> str:
        args = str_indent(
            str_mapping(
                {
                    "handler": self._handler,
                    "handler_args": self._handler_args,
                    "handler_kwargs": self._handler_kwargs,
                }
            )
        )
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
    def handler_args(self) -> tuple[Any]:
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
            A dictionary containing the keyword arguments that will be
                passed to the handler when it is called.
        """
        return self._handler_kwargs

    def handle(self) -> None:
        self._handler(*self._handler_args, **self._handler_kwargs)


class EventHandler(BaseEventHandlerWithArguments):
    r"""Implement a simple event handler.

    This class wraps a callable function or method and allows it to be
    executed as an event handler. The handler can be configured with
    positional and keyword arguments that will be passed when the
    handler is executed.

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

    def equal(self, other: Any) -> bool:
        if not isinstance(other, EventHandler):
            return False
        return (
            objects_are_equal(self.handler, other.handler)
            and objects_are_equal(self.handler_args, other.handler_args)
            and objects_are_equal(self.handler_kwargs, other.handler_kwargs)
        )


class ConditionalEventHandler(BaseEventHandlerWithArguments):
    r"""Implement a conditional event handler.

    This class extends ``BaseEventHandlerWithArguments`` to add
    conditional execution. The handler is executed only if the
    associated condition evaluates to ``True``. This is useful for
    scenarios where event handlers should only run under specific
    circumstances, such as periodic execution or state-based
    triggering.

    Args:
        handler: The callable function or method to be invoked when
            the event is triggered and the condition is ``True``.
        condition: The condition object that controls whether the
            handler is executed. The condition's ``evaluate`` method
            is called without arguments and must return a boolean
            value.
        handler_args: The positional arguments to pass to the handler
            when it is called. Default is ``None``.
        handler_kwargs: The keyword arguments to pass to the handler
            when it is called. Default is ``None``.

    Example:
        ```pycon
        >>> from minevent import ConditionalEventHandler, PeriodicCondition
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> handler = ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3))
        >>> handler
        ConditionalEventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
          (condition): PeriodicCondition(freq=3, step=0)
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
        condition: BaseCondition,
        handler_args: Sequence[Any] | None = None,
        handler_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(handler=handler, handler_args=handler_args, handler_kwargs=handler_kwargs)
        self._condition = condition

    def __repr__(self) -> str:
        args = str_indent(
            str_mapping(
                {
                    "handler": self._handler,
                    "handler_args": self._handler_args,
                    "handler_kwargs": self._handler_kwargs,
                    "condition": self._condition,
                }
            )
        )
        return f"{self.__class__.__qualname__}(\n  {args}\n)"

    @property
    def condition(self) -> BaseCondition:
        r"""Get the condition that controls handler execution.

        Returns:
            The condition that must evaluate to ``True`` for the
                handler to be executed.
        """
        return self._condition

    def equal(self, other: Any) -> bool:
        if not isinstance(other, ConditionalEventHandler):
            return False
        return (
            objects_are_equal(self.handler, other.handler)
            and objects_are_equal(self.handler_args, other.handler_args)
            and objects_are_equal(self.handler_kwargs, other.handler_kwargs)
            and objects_are_equal(self.condition, other.condition)
        )

    def handle(self) -> None:
        if self._condition.evaluate():
            super().handle()
