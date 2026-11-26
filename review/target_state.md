# `minevent`: target state and the changes to reach it

This document describes the design that `minevent` should have, then the changes to make to the
current implementation (`main`, `547656c`, #891) to get there. The design follows the properties of
the "How It Works" page (`docs/docs/architecture.md`), the reasons of the "Design Choices" page
(`docs/docs/design.md`) and the rules of `CLAUDE.md`. It replaces the previous version, whose ten
steps are all on `main` (#878 to #888).

The aim in one line: **one way to do each thing, no state that lies, and a merge that is tested.**
The design stays: an event is a string, a handler is a callable, the manager connects them, the
`Subscription` is the registration, the `Context` is the payload, a condition is a function. The
target removes one class and two methods, and adds no concept and no exported name.

Items are tagged **[verified]** (reproduced with a script, a test run, a measurement or a read of the
GitHub API, on an Apple laptop; scripts and prototype kept outside the repository) or **[reading]**
(from the code, the documents or the workflows). This change touches this document only: nothing in
`src`, `tests`, `docs` or `.github` is modified.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the **target**. Each design choice below exists to make one of them true by
construction. "Status" compares the row with `main`: **same** (stated and true today), **changed**
(the statement changes), **fixed** (claimed, or expected from a claim, but not true today) or **new**.

### Surface and registration

| #   | Property              | Statement                                                                                                                                                                                                                                                                                                                                      | Status  | Enforced by                           |
| --- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------- |
| P1  | Small surface         | Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Handler`, `Condition`, `PeriodicCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `in`. **One way to do each thing.**               | changed | `__all__` and review                  |
| P2  | Standard library only | No runtime dependency. `import minevent` starts no thread, emits no warning and writes no output and no log. Plain imports at the top of the modules; the import time is not a design input.                                                                                                                                                   | same    | `package_checks.py`, `test_import.py` |
| P3  | Events are strings    | An event name is a case-sensitive `str` (a `StrEnum` member is one, and is kept as given). The methods of the manager raise `TypeError` for another type, and `in` answers like a dict. The empty string is valid. Reading the manager never creates an event.                                                                                 | same    | `_check_event`                        |
| P4  | Validated at the door | Every argument is checked by the function that receives it: `TypeError` for a wrong type, `ValueError` for a wrong value. `once` is a `bool`; the integers of a condition are any integer (an object with `__index__`) but not a `bool`. A callable that cannot be called as documented is rejected. A rejection leaves the manager as it was. | fixed   | `add_event_handler`, `calls`          |
| P5  | Two calls             | A handler and a condition are called as `f()` or `f(context)`. A parameter that has a default keeps it. Without another parameter: `f()`. With exactly one, positional: `f(context)`. Anything else is rejected. Names and annotations are not checked. The signature is read once.                                                            | same    | `calls.adapt_call`                    |

### Dispatch

| #   | Property               | Statement                                                                                                                                                                                                                                                               | Status | Enforced by                         |
| --- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ----------------------------------- |
| P6  | Registration identity  | `add_event_handler` returns a new `Subscription` every time. `remove()` removes that registration only: `True` the first time, then `False`. **`active` is `True` exactly while the registration is in the manager**, and a `Subscription` cannot be copied or pickled. | fixed  | `Subscription`, `EventManager`      |
| P7  | Order                  | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                             | same   | the ordered `dict`                  |
| P8  | Snapshot, removal wins | A trigger visits the registrations that exist when it starts. An addition waits for the next trigger. A registration removed before its handler is called does not run, whoever removed it.                                                                             | same   | `Subscription._claim`               |
| P9  | `once` is at-most-once | A `once` registration is removed by an atomic claim after its condition and just before its handler. A false or raising condition does not consume it; a handler that raises does.                                                                                      | same   | `Subscription._claim`               |
| P10 | Synchronous by default | `trigger_event` never awaits: a coroutine function as handler in the snapshot raises `TypeError` before anything runs, and any other awaitable result raises it after the call. `atrigger_event` awaits one handler at a time. Conditions are synchronous.              | same   | `trigger_event`, `reject_awaitable` |

### Errors, payload, threads

| #   | Property                | Statement                                                                                                                                                                                                                   | Status  | Enforced by                        |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------- |
| P11 | Fail-fast, never masked | An exception of a handler or a condition propagates unchanged, with a note that names the event and what raised, and the next handlers are skipped. Adding the note and naming the callable never raise instead of it.      | same    | `calls.add_error_note`, `describe` |
| P12 | Bounded messages        | A message or a note of `minevent` is short whatever the size of the user data, **the event name included**: values are shown with `reprlib`, and a missing key lists at most 20 keys.                                       | fixed   | `reprlib`, `calls.describe_event`  |
| P13 | Payload is data         | One read-only `Context` per trigger, shared by the handlers and the conditions, from a mapping with `str` keys or a `Context` used as is. The keys that are checked are the keys that are stored. **`Context` is final.**   | changed | `Context`, `typing.final`          |
| P14 | Thread-safe registry    | The registry is protected by a reentrant lock. Handlers, conditions, `repr` and the finalizers of the removed handlers run outside the lock. This holds with and without the GIL.                                           | same    | `EventManager._lock`               |
| P15 | Exact condition         | `PeriodicCondition` counts every call once, from any number of threads, and can be copied and pickled. **Its `repr` shows the numbers as Python writes them.**                                                              | fixed   | the counter lock                   |
| P16 | Explicit, no state      | No global manager, no discovery, no side effect of a read. A manager is an ordinary object: always truthy, without a length, and it cannot be copied or pickled. `repr` shows what is registered. The library logs nothing. | changed | `__reduce__`                       |

### Engineering

| #   | Property            | Statement                                                                                                                                                                                                            | Status | Enforced by              |
| --- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------ |
| P17 | Typed               | Fully typed, `py.typed`, `ty check` clean, no cast and no ignore. A handler argument is typed `Handler`. The values of a `Context` are `Any`.                                                                        | same   | `ty check`               |
| P18 | Fast and linear     | About 0.3 µs for a trigger with one trivial handler, 0.07 µs for each extra one, 0.8 µs with a small dict, 5.5 µs for a registration plus its removal. A removal is O(1).                                            | same   | `tests/benchmarks/`      |
| P19 | One home per rule   | One documentation page states each rule; a docstring states what its own object does and names the page or the function that holds the rule.                                                                         | same   | review                   |
| P20 | Tested before merge | **No change reaches `main` without the result of its tests**, on Linux and macOS and on every supported Python (Windows is not supported). One required check says so. The suite stays small enough to get a result. | new    | the ruleset, `ci.yaml`   |
| P21 | Lean to maintain    | Every file of the repository serves a property of this table. The published distributions hold the package, not a part of the repository that cannot run.                                                            | new    | review, `pyproject.toml` |

Not guaranteed, and documented as such:

- **A removal in another thread** cannot stop a handler whose trigger has already passed the check.
- **Concurrent calls.** A registration without `once` is called by every thread that triggers its
  event, possibly at the same time. The state of a user handler or condition is its own concern.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **The start of a coroutine** (new in the list). `atrigger_event` reads the registrations and copies
  the payload when its coroutine starts to run, not when it is created: a task sees a change made to
  the dict, or a handler added, before it starts [verified].
- **A hidden coroutine.** A lambda, a `functools.cache` or a synchronous `functools.wraps` wrapper
  that returns a coroutine is only detected after its call by `trigger_event`: the handlers before it
  have run, and a `once` registration is consumed [verified].
- **Hidden generators.** A function that returns a generator does nothing.
- **An optional parameter never receives the context.** `def f(context=None)` gets `None`.
- **Names are not checked.** An unbound method `Model.save` is called with the context as `self`.
- **A signature that depends on Python.** `set.add`, `dict.clear` and `time.sleep` are rejected on
  3.11 and 3.12 and accepted from 3.13 [verified, 3.11 to 3.13].
- **A condition is evaluated by truthiness**, and it counts its calls, not the triggers.
- **A mutable value of the payload** can be mutated by a handler.
- **A huge integer in a message** on 3.11 and 3.12 raises the `ValueError` of Python.
- **Delayed release.** A manager with registrations is in a reference cycle; `reset()` releases the
  handlers at a known point.

## 2. Constraints on the target

1. **Simple and easy to maintain.** The target removes more than it adds: one class
   (`AfterNCondition`) and its base class, two methods of the manager, the import time tooling and the
   tests in the distribution.
2. **Breaking changes are fine.** The README says the API is unstable before 1.0, PyPI has `0.5.0`
   and `main` is `0.6.0a0` [verified]. No alias and no deprecation period; the changelog follows. The
   future state matters more than the past one: an earlier decision is reversed where it costs more
   than it gives (D1, D2, D6).
3. **Standard library only** (P2).
4. **A trigger does not get slower.** Measured in section 6.
5. **Settled decisions without a defect stay**: sequential async, fail-fast, the snapshot, the
   calling rule inferred from the signature (D4), one `Context` per trigger, values typed `Any`, a
   non-copyable manager, benchmarks nightly only, and the non-goals of the design page.

## 3. What differs today

**Baseline on `main`** [verified]: on Python 3.14.10, `ruff check`, `ruff format --check`,
`ty check`, `lint-imports`, `inv test.doctest` and `python tests/package_checks.py` pass, 796 unit
and integration tests pass with 100% line and branch coverage (347 statements), and
`pytest tests/benchmarks --benchmark-disable` passes (44 tests). The unit and integration tests also
pass on 3.11 (789, 7 skipped), 3.12 and 3.13 (791, 5 skipped), 3.14t and 3.15 (796).

No defect was found in the dispatch (P7 to P10). The findings are at the edges.

### Library

| #   | Finding                                                                                                                                                                                                                                                                                    | Property | Status     |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | ---------- |
| F1  | **`once` is not validated.** `add_event_handler("e", f, once="False")` runs `f` once, because the string is truthy, and `subscription.once` is `'False'`.                                                                                                                                  | P4       | [verified] |
| F2  | **`active` can lie.** `copy.copy(subscription)` returns a second object that stays `active` after the registration is removed, and whose `remove()` returns `False`. `Subscription(manager, "e", f)`, a public constructor, is `active` without being registered, and one test asserts it. | P6       | [verified] |
| F3  | **Only `int` is an integer.** `PeriodicCondition(x)` and `AfterNCondition(x)` reject an object with `__index__`, such as the integer types of numeric libraries that do not subclass `int`.                                                                                                | P4       | [verified] |
| F4  | **The `repr` of a condition misreads.** `PeriodicCondition(1000, start=2000)` shows `PeriodicCondition(freq=1,000, start=2,000, step=0)`, which reads as more arguments and is a syntax error if pasted.                                                                                   | P15      | [verified] |
| F5  | **The event name is not bounded.** With an event of 100,000 characters, the note of an exception has 100,060 characters and the message of the coroutine rejection 100,077.                                                                                                                | P12      | [verified] |
| F6  | **Two classes for one behaviour.** `AfterNCondition(n)` returns the same results as `PeriodicCondition(1, start=n)` (checked for `n` from 0 to 4, 20 calls). It costs a class, a private base class, their documentation and their tests.                                                  | P1       | [verified] |
| F7  | **`len(manager)` and `in` do not count the same thing.** With two handlers on `"a"`, `len(manager)` is 2, `events` is `['a']` and `"a" in manager` is `True`; the manager cannot be iterated. `__bool__` exists only to undo `__len__`.                                                    | P1, P16  | [verified] |
| F8  | **A subclass of `Context` has a hidden contract**: it must override `get` and `__contains__` with `__getitem__`, because both read the private dict.                                                                                                                                       | P13      | [reading]  |
| F9  | **Two statements are wrong or missing.** The comment of the lock says it is reentrant "so a handler can use the manager", while handlers run without the lock; and no page says when `atrigger_event` reads the payload.                                                                   | P19      | [reading]  |

### Engineering

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Property | Status                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------- |
| F10 | **Nothing gates a merge.** The branch protection and the ruleset of `main` have an empty list of required status checks, while the header of `ci.yaml` says that three checks are required.                                                                                                                                                                                                                                                                                             | P20      | [verified], 2026-11-26 |
| F11 | **Merges happen before any test result.** One CI run has about 130 jobs, 104 of them tests (13 runners, 8 Pythons). When read, none of the 104 test jobs of the merged pull requests #877 to #880 and #882 to #890 had a conclusion (those of #877, #884 and #890, looked at one by one, were queued). Of the last 100 runs of `ci.yaml`, 80 were cancelled, 20 queued or pending and none successful; the last success found is of 2026-11-23. Why the queue is long was not examined. | P20      | [verified], 2026-11-26 |
| F12 | **The classifier claims too much**: it says `Operating System :: OS Independent`, while Windows is not supported. The 13 runners are variants of Ubuntu and macOS, for a pure-Python package.                                                                                                                                                                                                                                                                                           | P20      | [reading]              |
| F13 | **The source distribution ships tests that cannot run.** It holds `tests/` but not `dev/`, so the collection of `tests/unit` fails with `No module named 'dev'`. It also moves `src/minevent` to `minevent`, so a test that reads `src` fails even with `dev/` added.                                                                                                                                                                                                                   | P21      | [verified]             |
| F14 | **The import time is tracked but is not a design input** (P2): a daily workflow, a benchmark, a trend script without unit tests and the tests of the benchmark helper, about 370 lines.                                                                                                                                                                                                                                                                                                 | P21      | [reading]              |

What is already right and must not regress: callables as handlers and conditions; the calling rule
checked once; the early rejection of coroutine and generator functions; one read-only `Context` per
trigger; the atomic `once` claim; the O(1) removal; the release of handlers outside the lock; errors
that are never replaced; the exact counter of the condition; 100% coverage.

## 4. Architecture

```text
add_event_handler(event, handler, *, once, condition)
        |   _check_event, once is a bool                       (4.1)
        |   calls.adapt_call, calls.has_kind                   -> two callables of (context)
        v
EventManager._subscriptions                  event -> ordered dict of Subscription, under the lock
        |   the manager alone sets Subscription._active        (4.2)
        v
trigger_event(event, context) / atrigger_event(event, context)
        |   snapshot under the lock, one Context (final)
        |   trigger_event only: an async handler in the snapshot -> TypeError, nothing has run
        v
for each subscription:
        removed, or guarded and not _claim(context)  -> skip   condition -> still active -> once
        _handler_call(context)
        awaitable result                             -> TypeError (sync) or await (async)
        exception          -> note with calls.describe and calls.describe_event      (4.3)
```

The modules and their jobs do not change:

| Module                   | Holds                                                                                   | Change   |
| ------------------------ | --------------------------------------------------------------------------------------- | -------- |
| `minevent/__init__.py`   | the exports, `__version__`                                                              | 4.4      |
| `minevent/calls.py`      | how user code is called and named: `Handler`, `adapt_call`, `has_kind`, `describe`, ... | 4.3      |
| `minevent/manager.py`    | `Subscription`, `EventManager`, `_check_event`, `_as_context`                           | 4.1, 4.2 |
| `minevent/conditions.py` | `Condition`, `PeriodicCondition`                                                        | 4.4      |
| `minevent/context.py`    | `Context`                                                                               | 4.5      |

### 4.1 The manager (F1, F7)

```python
# add_event_handler, with the other checks
if not isinstance(once, bool):
    msg = f"once must be a bool, but got {type(once).__qualname__}"
    raise TypeError(msg)
```

`__len__` and `__bool__` are deleted. An object without both is truthy, so `manager or default` keeps
its meaning. The number of handlers of an event is `len(manager.get_subscriptions(event))`, and
`repr(manager)` still shows the number for each event.

### 4.2 One owner of `active` (F2)

The constructor of a `Subscription` validates, and leaves `_active` to `False`. Only the manager
changes it, under the lock: `True` when it inserts the registration, `False` when it removes it. A
copy is refused like the copy of a manager:

```python
# Subscription
def __reduce__(self) -> NoReturn:
    msg = f"{type(self).__qualname__} cannot be copied or pickled: register the handler again"
    raise TypeError(msg)


# EventManager.add_event_handler
with self._lock:
    self._subscriptions.setdefault(event, {})[subscription] = None
    subscription._active = True
```

The comment of the lock states the real reason of an `RLock`: a signal handler or a finalizer that
runs while the lock is held can use the manager [reading].

### 4.3 The event name in messages (F5)

```python
# calls.py
_EVENT_REPR = reprlib.Repr()
_EVENT_REPR.maxstring = _EVENT_REPR.maxother = 200  # a StrEnum member is shown by maxother


def describe_event(event: str) -> str:
    return _EVENT_REPR.repr(event)
```

The note of `add_error_note` and the message of the coroutine rejection use it. The default limits of
`reprlib` (30) would cut ordinary names, such as the `repr` of a `StrEnum` member, hence 200.

### 4.4 One condition class (F3, F4, F6)

```python
def _to_int(value: object, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, SupportsIndex):
        msg = f"{name} must be an integer, got {type(value).__qualname__}"
        raise TypeError(msg)
    result = operator.index(value)
    if result < minimum:
        msg = f"{name} must be greater than or equal to {minimum}, got {result}"
        raise ValueError(msg)
    return result


class PeriodicCondition:
    def __init__(self, freq: SupportsIndex, *, start: SupportsIndex = 0) -> None:
        self._freq = _to_int(freq, "freq", 1)
        self._start = _to_int(start, "start", 0)
        self._step = 0
        self._lock = threading.Lock()

    def __call__(self) -> bool:
        with self._lock:
            step = self._step
            self._step = step + 1
        offset = step - self._start
        return offset >= 0 and offset % self._freq == 0

    # __getstate__, __setstate__, reset, freq and start: as today
    # __repr__: PeriodicCondition(freq=1000, start=0, step=0)
```

A warm-up is `PeriodicCondition(freq=1, start=n)`. `_CountingCondition`, `_next_step` and
`AfterNCondition` are deleted, and the class holds its own counter and lock.

### 4.5 A final `Context` (F8)

`Context` is decorated with `typing.final`, and the sentence of its docstring about the subclasses is
deleted. Nothing changes at run time; a type checker reports a subclass.

### 4.6 Repository (F10 to F14)

- **One small matrix.** `.github/workflow-config.json`, read by `durandtibo/workflow-config-action`
  through its `config` input, lists `ubuntu-latest` and `macos-latest`, and the same Python versions
  as today. `lib-get-test-matrix.yaml` checks out the repository, passes the file and uses `os_unix`.
  A CI run goes from 104 test jobs to 16. The versions and the runners stay in one place, as
  `CLAUDE.md` asks.
- **One required check.** `ci.yaml` ends with a job `ci` that depends on all the others, runs with
  `if: ${{ always() }}` and fails unless each result is `success`. The ruleset of `main` requires that
  check (a setting that a maintainer changes, not a pull request). The header of `ci.yaml` and
  `GUIDELINES.md` name it.
- **Supported systems.** Windows is not supported. `pyproject.toml` has the classifiers of Linux and
  macOS, and the README and the get started page state that Windows is not supported.
- **A source-only distribution**: `only-include = ["src"]` for the sdist. The wheel built from it holds
  the modules and `py.typed` [verified].
- **No import time tracking**: delete `ci-benchmark-import.yaml`, `dev/benchmark_import_trend.py`,
  `tests/benchmarks/test_import_benchmark.py`, `tests/unit/test_benchmark_import.py` and the
  `inv test.benchmark-import` task, and update the comments and the documents that name them.

## 5. Public API after the change

```text
from minevent import (
    Condition,  # Callable[[], bool] | Callable[[Context], bool]
    Context,  # Mapping[str, Any], final
    EventManager,
    Handler,  # Callable[[], object] | Callable[[Context], object]
    PeriodicCondition,  # (freq, *, start=0)
    Subscription,
    __version__,
)

manager.events  # list[str]
manager.get_subscriptions(event)  # tuple[Subscription, ...]
manager.add_event_handler(event, handler, *, once=False, condition=None)
manager.on(event, *, once=False, condition=None)  # decorator
manager.trigger_event(event, context=None, /)
await manager.atrigger_event(event, context=None, /)
manager.clear_event(event)
manager.reset()
event in manager

subscription.event, .handler, .once, .condition, .active
subscription.remove()  # bool
with subscription: ...  # removed on exit

condition(), condition.reset(), condition.freq, condition.start
```

### Migration

| Before                                                    | After                                                            |
| --------------------------------------------------------- | ---------------------------------------------------------------- |
| `AfterNCondition(n)`                                      | `PeriodicCondition(freq=1, start=n)`                             |
| `AfterNCondition(n).n`                                    | `.start`                                                         |
| `len(manager)`                                            | `sum(len(manager.get_subscriptions(e)) for e in manager.events)` |
| `once=1`, `once="yes"`                                    | `TypeError`: give `True` or `False`                              |
| `copy.copy(subscription)`                                 | `TypeError`                                                      |
| `Subscription(...)` built by hand is `active`             | it is not (the constructor stays internal)                       |
| `class MyContext(Context)`                                | reported by a type checker: wrap or build a `Context` instead    |
| `PeriodicCondition(freq=1,000, start=0, step=0)` (`repr`) | `PeriodicCondition(freq=1000, start=0, step=0)`                  |
| the whole event name in a note or a message               | shortened above 200 characters                                   |
| no note if the `repr` of a `str` subclass event raises    | a note with the placeholder of `reprlib`                         |

## 6. Evidence: a prototype

A prototype of 4.1 to 4.5 on a scratch copy of `main`. It has no final docstrings and no new tests.
Of 4.6, only the content of the distribution was tried.

**Behaviour** [verified, 3.11, 3.14 and 3.15, same results]:

| Probe                                   | `main`                   | Prototype           |
| --------------------------------------- | ------------------------ | ------------------- |
| `once="False"`                          | registered, runs once    | `TypeError`         |
| `freq` with `__index__`                 | `TypeError`              | `freq=3`            |
| `repr` of `PeriodicCondition(1000)`     | `freq=1,000`             | `freq=1000`         |
| copy of a subscription                  | a copy that stays active | `TypeError`         |
| hand-built subscription: `active`       | `True`                   | `False`             |
| note for an event of 100,000 characters | 100,060 characters       | 258                 |
| `len(manager)`, `bool(manager)`         | a number, `True`         | `TypeError`, `True` |
| pickle of a condition                   | works                    | works               |

**Existing tests** [verified, 3.14]: `ruff check`, `ruff format --check` and `ty check` are clean on
the `src` of the prototype. Without `test_conditions.py` (it imports the deleted classes), and with
a temporary alias for `AfterNCondition` in the other files: 665 tests pass and 48 fail, all for a
change of this plan: 42 use `len(manager)`, 3 expect the old `repr`, 2 expect a hand-built
subscription to be active and 1 expects no note for an event whose `repr` raises.

**Speed** (Python 3.14.10, µs, best of 15 repetitions, three runs) [verified]:

| Case                          |       `main` |    Prototype |
| ----------------------------- | -----------: | -----------: |
| trigger, no handler           | 0.20 to 0.23 |         0.20 |
| trigger, 1 handler            | 0.31 to 0.40 | 0.31 to 0.31 |
| trigger, 10 handlers          | 0.89 to 0.90 | 0.88 to 0.89 |
| trigger, 1 handler, dict      | 0.75 to 0.79 | 0.75 to 0.75 |
| registration plus removal     |   5.5 to 5.6 |   5.5 to 5.7 |
| call of a `PeriodicCondition` | 0.16 to 0.17 | 0.15 to 0.16 |

The ranges overlap: no cost was measured.

**Not verified**: the test suite and the speed on Linux; a numeric library (`__index__`
was tried with a stand-in class); the workflow changes of 4.6, which a pull request alone cannot
prove; the build of the documentation; and the nightly benchmark since #878, which had not run on
`main` after that change when it was read.

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own, stacked where it says
so. Each step updates the docstrings, `architecture.md`, `design.md`, the guide, the examples, the
README and the changelog for what it changes.

| Step | Branch                               | Change                                                                                      | Breaking | Fixes    |
| ---- | ------------------------------------ | ------------------------------------------------------------------------------------------- | -------- | -------- |
| 1    | `ci/gate-pull-requests`              | The matrix file, the `ci` job, `GUIDELINES.md` (4.6); then require the check in the ruleset | no       | F10, F11 |
| 2    | `bugfix/validate-once`               | The check of `once` (4.1)                                                                   | **yes**  | F1       |
| 3    | `bugfix/inactive-until-registered`   | The owner of `active`, `Subscription.__reduce__`, the comment of the lock (4.2)             | **yes**  | F2, F9   |
| 4    | `bugfix/shorten-event-names`         | `describe_event` (4.3)                                                                      | messages | F5       |
| 5    | `feat/single-counting-condition`     | Delete `AfterNCondition` and the base class (4.4)                                           | **yes**  | F6       |
| 6    | `feat/accept-index-integers` (on 5)  | `_to_int` (4.4)                                                                             | no       | F3       |
| 7    | `bugfix/plain-condition-repr` (on 6) | The `repr` of the condition (4.4)                                                           | output   | F4       |
| 8    | `feat/remove-manager-len`            | Delete `__len__` and `__bool__` (4.1); `repr` and `get_subscriptions` in the examples       | **yes**  | F7       |
| 9    | `feat/final-context`                 | `typing.final` (4.5)                                                                        | typing   | F8       |
| 10   | `docs/state-async-trigger-start`     | The limit of `atrigger_event` and the hidden coroutine of a cache (section 1)               | no       | F9       |
| 11   | `chore/remove-import-benchmark`      | Delete the import time tracking (4.6)                                                       | no       | F14      |
| 12   | `chore/source-only-sdist`            | `only-include = ["src"]`                                                                    | no       | F13      |
| 13   | `chore/state-windows-unsupported`    | The classifiers of Linux and macOS; state that Windows is not supported (4.6)               | no       | F12      |

Order of value if only part is taken: **1** (without it, no later step is known to work), then **2
and 3** (a program does something else than what was asked, or an object lies), then **5 and 8** (the
surface, best changed before `0.6.0` is published), then the others. Steps 3, 4 and 8 touch
`manager.py` and its tests: merge `origin/main` into the later ones.

Release `0.6.0` after the plan, so the release does not publish an API that changes again.

## 8. Tests and gates

Unit tests mirror the source tree; the rules of `CLAUDE.md` apply (one behaviour per test, `match` on
every `pytest.raises`, literals for expected values, a regression test that fails on `main`).

| Test                                                        | Behaviour                                                     | Step |
| ----------------------------------------------------------- | ------------------------------------------------------------- | ---- |
| `test_add_event_handler_once_not_bool` (parametrized)       | `TypeError` for `"False"`, `1`, `None`; the manager unchanged | 2    |
| `test_on_once_not_bool`                                     | `TypeError` when the decorator is applied                     | 2    |
| `test_subscription_active_never_registered` (inverted)      | `False`                                                       | 3    |
| `test_subscription_cannot_be_copied` (parametrized)         | `copy`, `deepcopy` and `pickle` raise                         | 3    |
| `test_describe_event` (parametrized)                        | short name, `StrEnum` member, long name as one literal        | 4    |
| `test_trigger_event_note_long_event`                        | the whole note as one literal                                 | 4    |
| `test_periodic_condition_freq_one_warm_up` (parametrized)   | `False` for `start` calls, then `True`                        | 5    |
| `test_to_int` (parametrized, with a class with `__index__`) | value, `bool`, `float`, below the minimum                     | 6    |
| `test_periodic_condition_repr_large_values`                 | `freq=1000`, without separator                                | 7    |
| `test_event_manager_bool_empty` (kept), `..._has_no_len`    | truthy; `len` raises                                          | 8    |
| `test_context_subclass_is_reported` (integration, `ty`)     | the type checker reports a subclass                           | 9    |
| `test_atrigger_event_reads_payload_at_start` (integration)  | the documented behaviour                                      | 10   |

Gates before each merge: `ruff check src tests`, `ruff format src tests`, `ty check`, `lint-imports`,
`pytest tests/unit tests/integration --cov=minevent --cov-branch` at 100%, `inv test.doctest`,
`python tests/package_checks.py`, and from step 1 the required check `ci`. Steps 5 and 8 compare the
benchmarks with `main` locally. Step 1 is checked with `actionlint` and with one run on its own pull
request that ends on both systems; step 12 with `uv build` and an installation of the sdist.

## 9. Decisions for the maintainers

- **D1. Delete `AfterNCondition`?** _Recommended: yes._ It is `PeriodicCondition(1, start=n)`; one
  class then holds the counter, the lock, the copy and the checks. The cost is real: `freq=1` reads
  less well than the name for a warm-up. Alternative: keep both classes and apply steps 6 and 7 to
  the base class.
- **D2. Remove `len(manager)`?** _Recommended: yes._ It has no obvious unit next to `in` and
  `events`, its use in the documentation is to show that a removal happened, which `repr` shows
  better, and `__bool__` goes with it. Alternative: keep it and say "registrations" everywhere.
- **D3. Make `Context` final?** _Recommended: yes._ A subclass has a contract that is easy to break
  for no use that the library has: a `Context` is data. Alternative: route `get` and `in` through
  `__getitem__`, which makes a missing key cost an error message again.
- **D4. Replace the calling rule by one shape, `f(context)`?** _Recommended: no._ It would remove the
  signature inspection, the differences between Python versions and the optional-parameter surprise.
  But `model.train` and `lambda: ...` could no longer be registered as they are, and a wrong signature
  would be found at the trigger instead of at registration.
- **D5. Two runners instead of 13?** _Recommended: yes._ The package is pure Python, so the images
  of one system add almost nothing, while merges happen before the results. Alternative: two
  runners on pull requests and the full list in a nightly run, at the price of a second matrix file.
- **D6. Stop tracking the import time?** _Recommended: yes._ P2 says it is not a design input, so a
  regression would not be acted on. Alternative: keep one test that bounds the number of modules.
- **D7. Break the reference cycle** between a manager and its subscriptions with a weak reference?
  _Recommended: no._ A subscription would have to handle a manager that is gone, to gain what
  `reset()` already gives.
- **D8. Require a condition to return a `bool`,** as `once` now must be one? _Recommended: no._ `once`
  is a constant that the user writes; the result of a condition is often the boolean of another
  library.

## 10. Not covered

- **The non-goals of the design page** (event objects, priorities, wildcards, weak references,
  collected errors, concurrent dispatch): unchanged.
- **The name of the event in the `Context`**, for a handler registered to several events: bind it with
  `functools.partial`.
- **Return values of handlers** and **typed payloads**: need their own design if users ask.
- **A condition on the number of triggers** instead of calls: write it from the payload.
- **The benchmark trend script** `dev/benchmark_trend.py` and the `bot-`, `release-` and `security-`
  workflows: not reviewed in depth.
- **`review/context_object_design.md`**: a past proposal, left as it is.

---

## Appendix: effect on the size of the package

| Item                         |      Today |  Prototype | Why                                                 |
| ---------------------------- | ---------: | ---------: | --------------------------------------------------- |
| exported names               | 7, version | 6, version | no `AfterNCondition`                                |
| classes in `conditions.py`   |          3 |          1 | no base class                                       |
| `conditions.py` statements   |         69 |         46 | one class, one check of the integers                |
| other `src` statements       |        278 |        286 | the check of `once`, `describe_event`, `__reduce__` |
| `src` statements             |        347 |        332 |                                                     |
| test jobs of a CI run        |        104 |         16 | two runners (not prototyped)                        |
| import time tracking (lines) |       ~370 |          0 | deleted (not prototyped)                            |
| runtime dependencies         |          0 |          0 |                                                     |

The prototype has no final docstrings, so no line count of `src` is given; the gate is the behaviour
(sections 1 and 8), not the size.
