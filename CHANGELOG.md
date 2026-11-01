# Changelog

All notable changes to `minevent` are documented in this file. The releases are also listed on
[GitHub](https://github.com/durandtibo/minevent/releases).

## Unreleased

Changes since `0.5.0` (the pull request numbers are in the commit history of `main`).

### Migration from `0.5.0`

- **Python**: `minevent` requires Python `>=3.11` (`0.5.0` supported `>=3.10`).
- **Dependencies**: `coola>=1.0,<2.0`, as in `0.5.0`.
- `EventManager.remove_event_handler` raises a `ValueError` (instead of a `RuntimeError`) when the
  handler is not registered. Use `missing_ok=True` to ignore a missing handler.
- Event names must be `str`: other types raise a `TypeError`.
- `has_event_handler(handler, event=None)` searches all the events only when `event` is `None`;
  an empty string is a regular event name.
- `trigger_event` runs the handlers registered when the trigger starts; handlers added or removed
  by a handler take effect at the next trigger.
- Reading the manager (`trigger_event`, `has_event_handler`, ...) no longer creates events.
- `EventHandler` copies `handler_kwargs`, rejects a `str` or `bytes` `handler_args`, and accepts a
  `condition` argument. `ConditionalEventHandler` is removed: use
  `EventHandler(handler, condition=condition)`.
- `PeriodicCondition` validates `freq` and has a `skip_first` option and a `reset` method.
- `__repr__` of `EventManager` is simpler.

### Added

- `EventManager.events`, `__contains__`, `clear_event` and `reset`.
- `trigger_event(event, **payload)` passes the keyword arguments to the handlers.
- `add_event_handler` returns a `Subscription` and has a `once` option.
- `atrigger_event` and `EventHandler.ahandle` to await coroutine handlers.
- Built-in conditions (`AlwaysCondition`, `OnceCondition`, `AfterNCondition`, `AndCondition`,
  `OrCondition`, `NotCondition`, `CallableCondition`); a function without argument that returns a
  boolean is accepted as a condition.
- The `EventManager` registry is thread-safe.
- `EventManager.get_event_handlers`, `__len__` and the `on` decorator.
- `has_event_handler` and `remove_event_handler` accept a `Subscription`.
- `Subscription` is a context manager and has an `active` property.
- `EventHandler(..., filter_payload=True)` passes only the payload keys the handler accepts.
- The exception of a handler has a note (`__notes__`) with the event and the handler that raised it.

### Fixed

- `Subscription.remove` removes only its own registration: calling it twice no longer removes the
  registration of another subscription of the same handler.

### Fixed

- `Subscription.remove` removes only its own registration: calling it twice no longer removes the
  registration of another subscription of the same handler.

### Changed

- Stricter type hints (`Callable[..., object]`, `Mapping`, `equal(other: object)`).
- `minevent.__version__` is resolved lazily from the package metadata.
