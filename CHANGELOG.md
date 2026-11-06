# Changelog

All notable changes to `minevent` are documented in this file. The releases are also listed on
[GitHub](https://github.com/durandtibo/minevent/releases).

## Unreleased

Changes since `0.5.0` (the pull request numbers are in the commit history of `main`).

### Migration from `0.5.0`

- **Python**: `minevent` requires Python `>=3.11` (`0.5.0` supported `>=3.10`).
- **Dependencies**: `minevent` has no dependency (`0.5.0` required `coola>=1.0,<2.0`).
- `EventManager.has_event_handler` and `remove_event_handler` are removed, and so are `equal` and
  `==` of event handlers and conditions: they are compared by identity. Keep the `Subscription`
  returned by `add_event_handler` and call `subscription.remove()` (it returns `False` when the
  registration is already removed), or use `manager.get_subscriptions(event)`.
- Event names must be `str`: other types raise a `TypeError`.
- `trigger_event` runs the handlers registered when the trigger starts; handlers added or removed
  by a handler take effect at the next trigger.
- Reading the manager (`trigger_event`, `get_subscriptions`, ...) no longer creates events.
- `EventHandler` copies `handler_kwargs`, rejects a `str` or `bytes` `handler_args`, and accepts a
  `condition` argument. `ConditionalEventHandler` is removed: use
  `EventHandler(handler, condition=condition)`.
- `BaseCondition` (with `evaluate` and `equal`) is removed. A condition is a function without
  argument that returns a boolean: implement `__call__` instead of `evaluate`, and call `condition()`
  instead of `condition.evaluate()`. Combine conditions with a function, for example
  `lambda: a() and b()`.
- `PeriodicCondition` validates `freq` and has a `skip_first` option and a `reset` method.
- `__repr__` of `EventManager` is simpler: `EventManager(events={'my_event': 1})`, and `__repr__` of
  `EventHandler` is one line.
- `EventManager.last_triggered_event` is removed.

### Added

- `EventManager.events`, `__contains__`, `clear_event` and `reset`.
- `trigger_event(event, **payload)` passes the keyword arguments to the handlers.
- `add_event_handler` returns a `Subscription` and has a `once` option.
- `atrigger_event` and `EventHandler.ahandle` to await coroutine handlers.
- Built-in condition `AfterNCondition`. A condition is any function without
  argument that returns a boolean (the `Condition` protocol), so a lambda is a condition.
- The `EventManager` registry is thread-safe.
- `EventManager.get_subscriptions`, `__len__` and the `on` decorator.
- `Subscription` is a context manager and has an `active` property.
- `EventManager.on(event, *, once, condition, filter_payload)` forwards the options of the handler (#767).
- `EventHandler(..., filter_payload=True)` passes only the payload keys the handler accepts.
- The exception of a handler has a note (`__notes__`) with the event and the handler that raised it.

### Fixed

- The note added to the exception of a handler is added once per distinct event and handler: an
  exception instance raised again, or a handler that triggers its own event, no longer accumulates
  identical notes (#766).
- `Subscription.remove` removes only its own registration: calling it twice no longer removes the
  registration of another subscription of the same handler.

### Changed

- Removing a registration is O(1) instead of O(n): the registry of an event is an ordered `dict`
  (#765). `Subscription.remove()` returns `False`, and no longer raises `KeyError`, for a
  subscription that was never registered in its manager.
- Stricter type hints (`Callable[..., object]`, `Mapping`, `BaseEventHandler.handle(**payload: object)`).
- `minevent.__version__` is resolved lazily from the package metadata.
- The package has no `all` extra (it had no optional dependency). The classifiers are
  `Development Status :: 3 - Alpha` and `Operating System :: OS Independent`.
- `EventManager.add_event_handler` raises a `TypeError` for an `event_handler` that is not a
  `BaseEventHandler` (a bare function used to fail at the first trigger with an `AttributeError`).
  Wrap the function with `EventHandler(func)`, or use `EventManager.on`.
- The awaitable check of a handler result uses `collections.abc` instead of `inspect`: each handler
  call is about 0.2 µs faster. A legacy generator-based coroutine (`types.coroutine`) is no longer
  detected as an awaitable.
- `Subscription` is defined in `minevent.manager` (the module `minevent.subscription` is removed);
  `from minevent import Subscription` is unchanged.
- The note of the exception of a handler names the event and the function of the handler, not the
  `repr` of the handler: a `repr` that raised used to replace the exception of the handler, and the
  arguments of the handler could make the note very long.
- Documentation: the `trigger_event` docstring, and the internal structure of `architecture.md`
  describe the current code.
- Documentation: the docstrings of `EventManager`, `Subscription`, `trigger_event`,
  `atrigger_event`, `clear_event` and `AfterNCondition` describe the `once` registrations, the
  notes of the exceptions, the `TypeError` for an awaitable and the thread safety. The quickstart
  and architecture pages no longer mention a synchronous-only system or `last_triggered_event`, and
  the architecture flows show the payload, the subscriptions and `ahandle`.
