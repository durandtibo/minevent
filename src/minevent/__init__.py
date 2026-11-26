r"""Contain the main features of the ``minevent`` package.

``minevent`` is a minimal event system with three concepts: an event (a
case-sensitive string), a handler (``Handler``) and an event manager
(``EventManager``) that registers the handlers and triggers the events.
A registration returns a ``Subscription``, which removes it. Every
handler and condition receives the payload of a trigger in a read-only
``Context``, and a ``Condition``, such as ``PeriodicCondition``,
controls when a handler runs.

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
    "Condition",
    "Context",
    "EventManager",
    "Handler",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]

from importlib.metadata import PackageNotFoundError, version

from minevent.calls import Handler
from minevent.conditions import Condition, PeriodicCondition
from minevent.context import Context
from minevent.manager import EventManager, Subscription

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # the package is not installed
    __version__ = "0.0.0"
