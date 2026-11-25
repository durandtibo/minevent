r"""Contain the main features of the ``minevent`` package.

``minevent`` is a minimal event system with three concepts: an event (a
case-sensitive string), a handler (any callable) and an event manager
(``EventManager``) that stores the handlers and triggers the events.

- ``EventManager.add_event_handler`` (or the ``on`` decorator) registers
  a handler and returns a ``Subscription``, the registration itself,
  that removes exactly that registration.
- ``EventManager.trigger_event`` runs the handlers in the order they
  were registered and passes its keyword arguments (the payload) to
  them in a read-only ``Context``. ``EventManager.atrigger_event`` also
  awaits the coroutine handlers.
- A condition is any function that returns a boolean, without parameter
  or with the ``Context`` of the trigger (``Condition``). ``PeriodicCondition`` and ``AfterNCondition`` are
  provided, and they control when a handler runs.

The package has no dependency, and ``__version__`` is the version of the
installed package.

Example:
    ```pycon
    >>> from minevent import EventManager
    >>> manager = EventManager()
    >>> _ = manager.add_event_handler("epoch_end", lambda context: print(f"epoch {context['epoch']}"))
    >>> manager.trigger_event("epoch_end", epoch=3)
    epoch 3

    ```
"""

from __future__ import annotations

__all__ = [
    "AfterNCondition",
    "Condition",
    "Context",
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
    return sorted([*globals(), "__version__"])
