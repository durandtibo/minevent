r"""Contain the main features of the ``minevent`` package.

``minevent`` is a minimal event system with three concepts: an event (a
case-sensitive string), an event handler (``BaseEventHandler``,
``EventHandler``) and an event manager (``EventManager``) that stores
the handlers and triggers the events. ``add_event_handler`` returns a
``Subscription`` that identifies a registration, and the conditions
(``Condition``, ``PeriodicCondition``, ``AfterNCondition``) control when
a handler runs. The package has no dependency.
"""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "BaseEventHandler",
    "Condition",
    "EventHandler",
    "EventManager",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]

from minevent.conditions import (
    AfterNCondition,
    Condition,
    PeriodicCondition,
)
from minevent.handlers import (
    BaseEventHandler,
    EventHandler,
)
from minevent.manager import EventManager, Subscription


def __getattr__(name: str) -> object:
    # PEP 562: the version is read from the metadata of the installed package the first time
    # it is used, because ``importlib.metadata`` is slow to import.
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

        try:
            value = version(__name__)
        except PackageNotFoundError:
            # Package is not installed, fallback if needed
            value = "0.0.0"
        globals()["__version__"] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted([*globals(), "__version__"])
