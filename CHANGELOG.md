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
- `EventHandler`, `BaseEventHandler` (and `ConditionalEventHandler`) are removed (#808). A handler is
  any callable, called as `handler(**payload)`, and the options of a registration are the
  keyword-only arguments of `add_event_handler` and `on`:

  - `add_event_handler("e", EventHandler(f))` becomes `add_event_handler("e", f)`.
  - `EventHandler(f, ["a"], {"k": 1})` becomes `functools.partial(f, "a", k=1)`. A payload key that
    repeats a bound keyword overrides it (it raised a `TypeError` for `handler_kwargs`).
  - `EventHandler(f, condition=c, filter_payload=True)` becomes
    `add_event_handler("e", f, condition=c, filter_payload=True)`.
  - `class H(BaseEventHandler): def handle(self, /, **payload)` becomes
    `class H: def __call__(self, **payload)`, and `async def ahandle` becomes `async def __call__`.

- `BaseCondition` (with `evaluate` and `equal`) is removed. A condition is a function without
  argument that returns a boolean: implement `__call__` instead of `evaluate`, and call `condition()`
  instead of `condition.evaluate()`. Combine conditions with a function, for example
  `lambda: a() and b()`.
- `PeriodicCondition` validates `freq` and has a `skip_first` option and a `reset` method.
- `__repr__` of `EventManager` is simpler: `EventManager(events={'my_event': 1})`.
- `EventManager.last_triggered_event` is removed.

### Added

- `EventManager.events`, `__contains__`, `clear_event` and `reset`.
- `trigger_event(event, **payload)` passes the keyword arguments to the handlers.
- `add_event_handler` returns a `Subscription` and has a `once` option.
- `atrigger_event` to await coroutine handlers.
- Built-in condition `AfterNCondition`. A condition is any function without
  argument that returns a boolean (the `Condition` protocol), so a lambda is a condition.
- The `EventManager` registry is thread-safe.
- `AfterNCondition.reset` restarts the counter, like `PeriodicCondition.reset` (#775).
- `EventManager.get_subscriptions`, `__len__` and the `on` decorator.
- `Subscription` is a context manager and has an `active` property.
- `EventManager.on(event, *, once, condition, filter_payload)` forwards the options of the handler (#767).
- `add_event_handler(..., filter_payload=True)` passes only the payload keys the handler accepts.
- The exception of a handler has a note (`__notes__`) with the event and the handler that raised it.

### Fixed

- The note added to the exception of a handler is added once per distinct event and handler: an
  exception instance raised again, or a handler that triggers its own event, no longer accumulates
  identical notes (#766).
- `repr(subscription)` names the handler (`Subscription(event='my_event', handler='print')`), so
  `manager.get_subscriptions(event)` can be read. The `TypeError` raised when `trigger_event` runs a
  handler that returns an awaitable names the function of the handler (it printed `repr(handler)`,
  which contains the arguments of a `functools.partial`). A test that matches `functools.partial(`
  in the message must match the function name.
- `Subscription.remove` removes only its own registration: calling it twice no longer removes the
  registration of another subscription of the same handler.

### Changed

- `bool(EventManager())` is always `True` (it was `False` for an empty manager), so
  `manager or default` is safe; use `len(manager) == 0` to test that a manager has no handler.
  `copy.copy`, `copy.deepcopy` and `pickle` of an `EventManager` raise a `TypeError` (`copy.copy`
  used to share the registry silently): create a new manager (#771).
- `Subscription.active` reads the registry of the manager instead of a copy of the state, so it is
  `False` for a subscription that was never registered (it was `True`). `reset` and `clear_event` no
  longer walk the registrations to flip a flag (#772).
- Removing a registration is O(1) instead of O(n): the registry of an event is an ordered `dict`
  (#765). `Subscription.remove()` returns `False`, and no longer raises `KeyError`, for a
  subscription that was never registered in its manager.
- Stricter type hints (`Callable[..., object]`, payload typed `object`).
- The `Subscription` owns the options of its registration: its internal constructor takes
  `once`, `condition` and `filter_payload` as keyword-only arguments (it took a private `_Options`
  tuple, now removed), and the trigger no longer reads the `once` flag of a subscription. No
  behaviour change.
- `minevent.__version__` is resolved lazily from the package metadata.
- `import minevent` is cheap: the `DEBUG` logs of the `minevent.manager` logger are removed and
  `inspect` is imported when `filter_payload=True` is used, so `import minevent` no longer imports
  `logging`, `inspect`, `asyncio` or `importlib.metadata` (it loaded 40 modules in 16 ms, and it
  loads about a third of them in about 6 ms, Python 3.14). To trace a registration, read
  `manager.get_subscriptions(event)` or wrap the handler (#810).
- The package has no `all` extra (it had no optional dependency). The classifiers are
  `Development Status :: 3 - Alpha` and `Operating System :: OS Independent`.
- `EventManager.add_event_handler` accepts any callable, and has the keyword-only options
  `condition` and `filter_payload` next to `once`. It raises a `TypeError` for a `handler` that is
  not callable or a `condition` that is neither `None` nor callable (a bare function used to fail at
  the first trigger with an `AttributeError`). `EventManager.on` is the decorator form of
  `add_event_handler` (#807).
- `Subscription.event_handler` is renamed `Subscription.handler`, and `Subscription` has the read-only
  properties `condition` and `filter_payload` (#807).
- The note of the exception of a handler names the function under a `functools.partial` (it was
  `partial`) (#807).
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
  the architecture flows show the payload and the subscriptions.
- Documentation: `architecture.md` has the 18 properties of the package (P1 to P18), a list of the
  behaviors that are not guaranteed, and describes handlers as callables and the options of a
  registration (#809). The README, the guide, the quickstart and the FAQ use callables (#808).
- Documentation: the properties table of `architecture.md` lists the 8 public members of
  `EventManager`, "Design Decisions" and "Conclusion" are removed, `CONTRIBUTING.md` uses the invoke
  tasks, and `review/suggestions.md` is deleted (#770).
