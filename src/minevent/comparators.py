from __future__ import annotations

__all__ = ["EventHandlerEqualityOperator"]

import logging
from typing import Any

from coola import BaseEqualityOperator, BaseEqualityTester, EqualityTester

from minevent.handlers import BaseEventHandler

logger = logging.getLogger(__name__)


class EventHandlerEqualityOperator(BaseEqualityOperator[BaseEventHandler]):
    r"""Implements an equality operator for ``BaseEventHandler`` objects.

    Example usage:

    .. code-block:: pycon

        >>> from coola import EqualityTester
        >>> from minevent import EventHandler, EventHandlerEqualityOperator
        >>> def hello_handler() -> None:
        ...     print("Hello!")
        ...
        >>> comparator = EventHandlerEqualityOperator()
        >>> comparator.equal(
        ...     EqualityTester(), EventHandler(hello_handler), EventHandler(hello_handler)
        ... )
        >>> True
    """

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__)

    def clone(self) -> EventHandlerEqualityOperator:
        return self.__class__()

    def equal(
        self,
        tester: BaseEqualityTester,
        object1: BaseEventHandler,
        object2: Any,
        show_difference: bool = False,
    ) -> bool:
        if object1 is object2:
            return True
        if not isinstance(object2, BaseEventHandler):
            if show_difference:
                logger.info(f"object2 is not a `BaseEventHandler` object: {type(object2)}")
            return False
        object_equal = object1.equal(object2)
        if show_difference and not object_equal:
            logger.info(
                f"`BaseEventHandler` objects are different\nobject1=\n{object1}\n"
                f"object2=\n{object2}"
            )
        return object_equal


if not EqualityTester.has_operator(BaseEventHandler):  # pragma: no cover
    EqualityTester.add_operator(BaseEventHandler, EventHandlerEqualityOperator())