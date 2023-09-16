from __future__ import annotations

__all__ = [
    "BaseEventHandler",
    "BaseEventHandlerWithArguments",
    "ConditionalEventHandler",
    "EventHandler",
]

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any

from coola import objects_are_equal
from coola.utils import str_indent, str_mapping

from minevent.conditions import BaseCondition


class BaseEventHandler(ABC):
    r"""Defines the base class to implement an event handler.

    A child class has to implement the following methods:

        - ``handle``
        - ``equal``

    Example usage:

    .. code-block:: pycon

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
    """

    def __eq__(self, other: Any) -> bool:
        return self.equal(other)

    @abstractmethod
    def equal(self, other: Any) -> bool:
        r"""Compares two event handlers.

        Args:
        ----
            other: Specifies the other object to compare with.

        Returns:
        -------
            bool: ``True`` if the two event handlers are equal,
                otherwise ``False``.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> handler = EventHandler(hello_handler)
            >>> handler.equal(EventHandler(hello_handler))
            True
            >>> handler.equal(EventHandler(print, handler_args=["Hello!"]))
            False
        """

    @abstractmethod
    def handle(self) -> None:
        r"""Handles the event.

        Example usage:

        .. code-block:: pycon

            >>> from minevent import EventHandler
            >>> def hello_handler() -> None:
            ...     print("Hello!")
            ...
            >>> handler = EventHandler(hello_handler)
            >>> handler.handle()
            Hello!
        """


class BaseEventHandlerWithArguments(BaseEventHandler):
    r"""Defines a base class to implement an event handler with
    positional and/or keyword arguments.

    A child class has to implement the ``equal`` method.

    Args:
    ----
        handler (``Callable``): Specifies the handler.
        handler_args (``Sequence`` or ``None``, optional): Specifies
            the positional argument of the handler.
            Default: ``None``
        handler_kwargs (dict or ``None``, optional): Specifies the
            arbitrary keyword arguments of the handler.
            Default: ``None``

    Example usage:

    .. code-block:: pycon

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
    """

    def __init__(
        self,
        handler: Callable,
        handler_args: Sequence | None = None,
        handler_kwargs: dict | None = None,
    ) -> None:
        if not callable(handler):
            raise TypeError(f"handler is not callable: {handler}")
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
        r"""Callable: The handler."""
        return self._handler

    @property
    def handler_args(self) -> tuple:
        r"""``tuple``: Variable length argument list of the handler."""
        return self._handler_args

    @property
    def handler_kwargs(self) -> dict:
        r"""``dict``: Arbitrary keyword arguments of the handler."""
        return self._handler_kwargs

    def handle(self) -> None:
        self._handler(*self._handler_args, **self._handler_kwargs)


class EventHandler(BaseEventHandlerWithArguments):
    r"""Implements a simple event handler.

    Example usage:

    .. code-block:: pycon

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
    r"""Implements a conditional event handler.

    The handler is executed only if the condition is ``True``.

    Args:
    ----
        handler (``Callable``): Specifies the handler.
        condition (``Callable``): Specifies the condition for this
            event handler. The condition should be callable without
            arguments.
        handler_args (``Sequence`` or ``None``, optional): Specifies
            the  positional arguments of the handler.
            Default: ``None``
        handler_kwargs (dict, optional): Specifies the arbitrary
            keyword arguments of the handler. Default: ``None``

    Example usage:

    .. code-block:: pycon

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
    """

    def __init__(
        self,
        handler: Callable,
        condition: BaseCondition,
        handler_args: Sequence | None = None,
        handler_kwargs: dict | None = None,
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
        r"""``BaseCondition``: The condition."""
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
