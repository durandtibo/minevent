r"""Contain the main features of the ``minevent`` package.

``minevent`` is a minimal event system with three concepts: an event (a
case-sensitive string), a handler (``Handler``) and an event manager
(``EventManager``) that registers the handlers and triggers the events.
A registration returns a ``Subscription``, the handlers receive the
payload of a trigger in a read-only ``Context``, and a ``Condition``,
such as ``PeriodicCondition`` or ``AfterNCondition``, controls when a
handler runs.

The package has no dependency, and ``__version__`` is the version of the
installed package.

Example:
    ```pycon
    >>> from minevent import EventManager
    >>> manager = EventManager()
    >>> _ = manager.add_event_handler("epoch_end", lambda context: print(f"epoch {context['epoch']}"))
    >>> manager.trigger_event("epoch_end", {"epoch": 3})
    epoch 3

    ```
"""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "Condition",
    "Context",
    "EventManager",
    "Handler",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]

from minevent.calls import Handler
from minevent.conditions import (
    AfterNCondition,
    Condition,
    PeriodicCondition,
)
from minevent.context import Context
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
    # A set: ``__version__`` is in the globals once it has been read.
    return sorted({*globals(), "__version__"})
