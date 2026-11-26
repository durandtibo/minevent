# Changelog

All notable changes to `minevent` are documented in this file. The releases are also listed on
[GitHub](https://github.com/durandtibo/minevent/releases).

## Unreleased

Changes since `0.5.0` (the pull request numbers are in the commit history of `main`). The rules of
the new API are in the
[how it works page](https://durandtibo.github.io/minevent/main/architecture/).

### Migration from `0.5.0`

- **Python**: `minevent` requires Python `>=3.11` (`0.5.0` supported `>=3.10`).
- **Dependencies**: `minevent` has no dependency (`0.5.0` required `coola>=1.0,<2.0`).
- **Handlers**: `EventHandler`, `BaseEventHandler`, `BaseEventHandlerWithArguments` and
  `ConditionalEventHandler` are removed. A handler is a callable that needs no argument or only the
  context, and the options of a registration are the keyword-only arguments of `add_event_handler`
  and `on`:

  | `0.5.0`                                       | Now                                                                |
  | --------------------------------------------- | ------------------------------------------------------------------ |
  | `add_event_handler("e", EventHandler(f))`     | `add_event_handler("e", f)`                                        |
  | `EventHandler(f, ["a"], {"k": 1})`            | `functools.partial(f, "a", k=1)`                                   |
  | `ConditionalEventHandler(f, c)`               | `add_event_handler("e", f, condition=c)`                           |
  | `class H(BaseEventHandler): def handle(self)` | `class H: def __call__(self)`                                      |
  | `EventHandler(print, ["a"])`                  | `lambda: print("a")` (a callable that accepts `*args` is rejected) |

- **Calling rule**: a parameter of a handler or of a condition that has a default keeps it, and a
  callable that needs anything else than nothing or the context raises a `TypeError` at registration
  (`*args`, `**kwargs`, two parameters, a keyword-only parameter, a signature that cannot be
  inspected), as does a generator or async generator function, or a callable object whose
  `__call__` is one.
- **Conditions**: `BaseCondition` (with `evaluate` and `equal`) is removed. A condition is a
  function that returns a boolean: implement `__call__` instead of `evaluate`, and call
  `condition()` instead of `condition.evaluate()`. Combine conditions with a function, for example
  `lambda: a() and b()`. A coroutine function, or an object with `async def __call__`, used as a
  condition raises a `TypeError` at registration, and a condition that returns an awaitable another
  way raises it at the trigger.
- **Registrations**: `EventManager.has_event_handler` and `remove_event_handler` are removed, and so
  is the comparison of handlers and conditions with `equal` and `==`. Keep the `Subscription`
  returned by `add_event_handler` and call `subscription.remove()` (it returns `False` when the
  registration is already removed, where `remove_event_handler` raised a `RuntimeError`), or use
  `manager.get_subscriptions(event)`.
- **Typing**: a handler argument is typed `Handler`, so a type checker reports a handler that needs
  two arguments, a keyword-only argument or an argument of another type. Annotate the parameter of a
  handler `Context` (or `Mapping`).
- **Events**: an event name must be a `str`, such as a `StrEnum` member (other types, a member of
  a plain `Enum` included, raise a `TypeError`; they were converted with `str` at registration).
- **Dispatch**: a trigger runs the registrations that exist when it starts: a handler added by a
  running handler runs at the next trigger, and a registration removed before its handler is
  called, by another handler or by its own condition, does not run. Triggering an event without
  handler no longer creates it.
- **Manager**: `last_triggered_event` is removed, the `repr` is simpler
  (`EventManager(events={'my_event': 1})`), a manager cannot be copied or pickled, and nothing is
  logged (`0.5.0` logged at the `DEBUG` level).
- **Async**: `trigger_event` raises a `TypeError` before anything runs if a handler of the event is
  a coroutine function, and after the call of a handler that returns an awaitable another way (the
  coroutine was silently dropped): use `atrigger_event`.

### Added

- `trigger_event(event, context=None, /)` passes the mapping `context` (a dict, or a `Context`) to
  the handlers and the conditions in one read-only `Context` per trigger.
- `minevent.Context`, an immutable mapping from `str` to values: `context[key]` (a `KeyError` lists
  at most 20 of the available keys), `get`, `in`, `len`, iteration and `==`. Its values are typed
  `Any`, and it can be copied, deep-copied and pickled if its values can. `get` and `in` cost the
  same for a present key and a missing one, whatever the number of keys. The mapping is read once,
  so the keys that are checked are the keys that are stored.
- `atrigger_event` to await coroutine handlers.
- The error messages stay short whatever the size of the data: values are shown with `reprlib`.
- `add_event_handler` returns a `Subscription`, which removes exactly its registration, is a context
  manager and has the properties `event`, `handler`, `once`, `condition` and `active`.
- The keyword-only options `once` (run at most once, the first time the condition is `True`, even
  with several threads) and `condition` of `add_event_handler`, and the `on` decorator.
- `EventManager.events`, `get_subscriptions`, `clear_event`, `__len__` and `__contains__`. A manager
  is always truthy.
- `AfterNCondition`, and the `start` option and the `reset` method of `PeriodicCondition`,
  which now validates `freq`. The type aliases `Handler` and `Condition`.
- The registry of `EventManager` is thread-safe, and a removal is O(1). The handlers, the
  conditions and the finalizers of the removed handlers run outside its lock.
- `PeriodicCondition` and `AfterNCondition` count every call once from any number of threads, with
  and without the GIL, and can be copied and pickled.
- The exception of a handler or a condition has a note with the event and what raised it: the
  handler, or the condition and its handler. Neither naming the callable nor adding the note replaces
  the exception.
- `import minevent` starts no thread, emits no warning and writes no output and no log.
  `__version__` is read from the package metadata at the import.
- Documentation: an [examples page](https://durandtibo.github.io/minevent/main/examples/) and a
  user guide, and the FAQ is removed (#861). The documentation describes the current library, with
  a "How It Works" page for the rules and a "Design Choices" page for the trade-offs (#876).
- Packaging: the classifiers are `Development Status :: 3 - Alpha`, `Operating System :: MacOS` and
  `Operating System :: POSIX :: Linux`, and there is no `all` extra. Windows is not supported
  (#894). The license is given by its SPDX expression only, without a `License ::` classifier (#890).
- Development: `import-linter` checks the layering of the modules, and the invoke tasks come from
  `invoke-tasklib` `>=0.1.0` (#890).
- Releases: the files published to PyPI are signed, and the GitHub release has a SLSA provenance
  file. A GitHub build provenance attestation is stored. A manual run only publishes a pre-release
  (#891).
- Development: each pull request runs `tests/package_checks.py` (#851), and the benchmarks run
  nightly only. A benchmark run compares the medians with the ones of the last finished run of
  `main`. The nightly package test runs the checks of the tag of the installed version.
