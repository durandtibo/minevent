# Changelog

All notable changes to `minevent` are documented in this file. The releases are also listed on
[GitHub](https://github.com/durandtibo/minevent/releases).

## 0.6.0

Changes since `0.5.0` (the pull request numbers are in the commit history of `main`). The rules of
the new API are in the
[how it works page](https://durandtibo.github.io/minevent/main/architecture/).

### Migration from `0.5.0`

- **Python**: `minevent` requires Python `>=3.11` (`0.5.0` supported `>=3.10`).
- **Dependencies**: `minevent` has no dependency (`0.5.0` required `coola>=1.0,<2.0`).
- **Handlers**: `EventHandler`, `BaseEventHandler`, `BaseEventHandlerWithArguments` and
  `ConditionalEventHandler` are removed. A handler is a callable that is called with the context of
  the trigger, and the options of a registration are the keyword-only arguments of
  `add_event_handler` and `on`:

  | `0.5.0`                                       | Now                                      |
  | --------------------------------------------- | ---------------------------------------- |
  | `add_event_handler("e", EventHandler(f))`     | `add_event_handler("e", lambda _: f())`  |
  | `EventHandler(f, ["a"], {"k": 1})`            | `lambda _: f("a", k=1)`                  |
  | `ConditionalEventHandler(f, c)`               | `add_event_handler("e", f, condition=c)` |
  | `class H(BaseEventHandler): def handle(self)` | `class H: def __call__(self, context)`   |
  | `EventHandler(print, ["a"])`                  | `lambda _: print("a")`                   |

- **Calling rule**: a handler and a condition are always called as `f(context)`. Exactly one
  parameter must lack a default, and it must be positional. Anything else raises a `TypeError` at
  registration (a function without parameter, `def f(context=None)`, `*args`, `**kwargs`, two
  parameters, a keyword-only parameter, a signature that cannot be inspected), as does a generator or
  async generator function, or a callable object whose `__call__` is one. Write `def f(_)` for a
  handler that ignores the context (#920).
- **Conditions**: `BaseCondition` (with `evaluate` and `equal`) is removed. A condition is a
  function of the context that returns a boolean: implement `__call__(self, context)` instead of
  `evaluate`, and call `condition(context)` instead of `condition.evaluate()`, also for a
  `PeriodicCondition`, which ignores the context. Combine conditions with a function, for example
  `lambda context: a(context) and b(context)`. A coroutine function, or an object with
  `async def __call__`, used as a condition raises a `TypeError` at registration, and a condition
  that returns an awaitable another way raises it at the trigger.
- **Registrations**: `EventManager.has_event_handler` and `remove_event_handler` are removed, and so
  is the comparison of handlers and conditions with `equal` and `==`. Keep the `Subscription`
  returned by `add_event_handler` and call `subscription.remove()` (it returns `False` when the
  registration is already removed, where `remove_event_handler` raised a `RuntimeError`), or use
  `manager.get_subscriptions(event)`.
- **Typing**: a handler argument is typed `Handler`, so a type checker reports a handler without
  parameter, or one that needs two arguments, a keyword-only argument or an argument of another
  type. Annotate the parameter of a handler `Context` (or `Mapping`).
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
  so the keys that are checked are the keys that are stored. `Context` is final: a type checker
  reports a subclass (#902).
- `atrigger_event` to await coroutine handlers.
- The error messages stay short whatever the size of the data: values are shown with `reprlib`, and
  an event name is shortened above 200 characters in a note or a message (#897). So are the
  arguments of `PeriodicCondition` in its `ValueError` (#912).
- `add_event_handler` returns a `Subscription`, which removes exactly its registration, is a context
  manager and has the properties `event`, `handler`, `once`, `condition` and `active`. `active` is
  `True` exactly while the registration is in the manager, and a `Subscription` cannot be copied or
  pickled (#896). Its `repr` shows the event and the name of the handler, then `once=True`, the
  name of the condition and `active=False` when they apply (#913).
- The keyword-only options `once` (run at most once, the first time the condition is `True`, even
  with several threads) and `condition` of `add_event_handler`, and the `on` decorator. `once` must
  be a `bool`: another value, such as `1` or `"False"`, raises a `TypeError` (#895).
- `EventManager.events`, `get_subscriptions`, `clear_event` and `__contains__`. A manager is always
  truthy.
- The `start` option, the `reset` method and the read-only `step` property of `PeriodicCondition`,
  which now validates `freq`. `PeriodicCondition(freq=1, start=n)` is a warm-up, `False` for the
  first `n` calls. Its `repr` shows `freq`, `start` and `step` without thousands separator, for
  example `PeriodicCondition(freq=1000, start=0, step=0)` (#898, #900, #919).
- The type aliases `Handler` and `Condition`.
- The registry of `EventManager` is thread-safe, and a removal is O(1). The handlers, the
  conditions and the finalizers of the removed handlers run outside its lock.
- `PeriodicCondition` counts every call once from any number of threads, with and without the GIL,
  and can be copied and pickled.
- The exception of a handler or a condition has a note with the event and what raised it: the
  handler, or the condition and its handler. Neither naming the callable nor adding the note replaces
  the exception.
- `import minevent` starts no thread, emits no warning and writes no output and no log.
  `__version__` is read from the package metadata at the import.
- Documentation: an [examples page](https://durandtibo.github.io/minevent/main/examples/) and a
  user guide, and the FAQ is removed (#861). The documentation describes the current library, with
  a "How It Works" page for the rules, the guarantees, the limits and the public API, which is what
  `minevent` exports, and a "Design Choices" page for the trade-offs. Each rule has one page, and the
  reference is one page that shows what `minevent` exports
  (#876, #904, #911, #921, #923, #931, #934).
- Packaging: the classifiers are `Development Status :: 3 - Alpha`, `Operating System :: MacOS` and
  `Operating System :: POSIX :: Linux`, and there is no `all` extra. Windows is not supported
  (#894). The license is given by its SPDX expression only, without a `License ::` classifier (#890).
- Development: `import-linter` checks the layering of the modules, and rejects a module that is in no
  layer. The invoke tasks come from `invoke-tasklib` `>=0.1.0`, and the documentation no longer
  depends on `mkdocs-include-markdown-plugin` (#890, #914).
- Releases: the files published to PyPI are signed, and the GitHub release has a SLSA provenance
  file. A GitHub build provenance attestation is stored. A manual run only publishes a pre-release
  (#891).
- Development: each pull request runs `tests/package_checks.py` (#851), and the benchmarks run
  nightly only. A benchmark run compares the medians with the ones of the last finished run of
  `main`. The nightly package test runs the checks of the tag of the installed version.
- Packaging: the source distribution holds the sources and the tests in the layout of the repository
  (`src/minevent/` next to `tests/`), so the tests pass from it. It leaves out the test of a script
  of `dev/`. The wheel holds the package only (#915).
- Development: `pyright` checks the source too (`inv types.check --complete`), and `Context.get`
  returns the default for a key that is not a `str` even if it is equal to one (#926).
- Development: the CI type checks with `pyright` too, and a weekly workflow updates
  `dev/config/package_versions.json` (#927).
- Development: the `check_*` functions are renamed to `validate_*`, in the package
  (`calls.validate_signature`, which is not part of the public API) and in the tests, except the
  checks of `tests/package_checks.py` (#931).
- Documentation: the examples add recipes to start background work from a handler and to resume a
  training, and the recipe to register a handler only once works with a bound method (#932).
- Documentation: each rule has one home. The docstrings of `validate_signature`, `add_event_handler`
  and `conditions` link to the calling rule, and the behaviour of `Subscription`,
  `PeriodicCondition` and `Context` is left to their docstrings (#933).
- Development: a broken link or anchor between the documentation pages fails the build, in the CI and
  in the releases too (#936).
- Development: the CI runs the unit and integration tests from the source distribution on every
  `sdist` build (#937).
- Development: the script of the package versions has unit and integration tests, which the source
  distribution leaves out (#938).
- Release: the `Changelog` link of the package points to this file, and the security policy supports
  `0.6.x` (#939).
- Documentation: the docstrings match the current calling rule and name how a coroutine handler is
  triggered, the README adds examples of the conditions, the removal and the coroutine handlers, and
  the workflow guidelines match the workflows (#941).
- Documentation: the pages explain the current library: the home page says what it is for, "How It
  Works" shows how the parts fit and groups the limits, "Design Choices" groups the trade-offs under
  the goals of the library, and the examples are grouped by topic (#942).
