# `minevent`: target state and the changes to reach it

This document describes the design that `minevent` should have, then the changes to make to the
current implementation (`main`, `06928d9`, #876) to get there. The design follows the properties of
the "How It Works" page (`docs/docs/architecture.md`), with one of them relaxed, and the rules of
`CLAUDE.md`. It replaces the previous version, whose eleven steps are all on `main`.

The aim in one line: **what you register is either called as documented or rejected before anything
runs, and an error from `minevent` never hides yours.** The design stays: an event is a string, a
handler is a callable, the manager connects them, the `Subscription` is the registration, the
`Context` is the payload, a condition is a function. No concept and no exported name is added.

Items are tagged **[verified]** (reproduced with a script, a test run or a measurement, Apple
laptop, scripts and prototype kept outside the repository) or **[reading]** (from the code, the
documents or the workflows). This change touches this document only: nothing in `src`, `tests`,
`docs` or `.github` is modified.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the **target**. Each design choice below exists to make one of them true by
construction. "Status" compares the row with `docs/docs/architecture.md` today: **same**,
**changed** (the statement changes), **fixed** (already claimed, or expected from a claim, but not
true today) or **new**.

### Surface and registration

| #   | Property              | Statement                                                                                                                                                                                                                                                                                                                                                                 | Status  | Enforced by                           |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------- |
| P1  | Small surface         | Seven exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Handler`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`. One way to do each thing.    | same    | `__all__` and review                  |
| P2  | Standard library only | No runtime dependency. `import minevent` starts no thread, emits no warning and writes no output and no log. The modules of the standard library, `typing`, `logging`, `inspect`, `asyncio` and `importlib.metadata` included, **may be imported at the top of a module**: the import time is not a design input. A module that is not needed is not imported on purpose. | changed | `package_checks.py`, `test_import.py` |
| P3  | Events are strings    | An event name is a case-sensitive `str` (a `StrEnum` member is one, and is kept as given). The methods of the manager raise `TypeError` for another type, and `in` answers like a dict. The empty string is valid. Reading the manager never creates an event.                                                                                                            | same    | `_check_event`                        |
| P4  | Validated at the door | `add_event_handler` and `on` reject, with a `TypeError` that names the argument and the value, and leave the manager unchanged: a non-`str` event, a non-callable, a signature that P5 rejects, a generator or async generator function, and a coroutine function used as a condition. **A callable object is judged by its `__call__`.**                                 | fixed   | `calls.adapt_call`, `calls.has_kind`  |
| P5  | Two calls             | A handler and a condition are called as `f()` or `f(context)`. A parameter that has a default keeps it. Without another parameter: `f()`. With exactly one, positional: `f(context)`. Anything else, `*args`, `**kwargs` and a signature that cannot be inspected included, is rejected. Names and annotations are not checked. The signature is read once.               | same    | `calls.adapt_call`                    |

### Dispatch

| #   | Property               | Statement                                                                                                                                                                                                                                                                                                     | Status  | Enforced by                         |
| --- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------------------------------- |
| P6  | Registration identity  | `add_event_handler` returns a new `Subscription` every time. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` until the registration is removed, by whatever means.                                                                                         | same    | `Subscription`                      |
| P7  | Order                  | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                   | same    | the ordered `dict`                  |
| P8  | Snapshot, removal wins | A trigger visits the registrations that exist when it starts. An addition waits for the next trigger. **A registration removed before its handler is called does not run, whoever removed it: another handler, or its own condition**, with or without `once`.                                                | fixed   | `Subscription._claim`               |
| P9  | `once` is at-most-once | A `once` registration is removed by an atomic claim after its condition and just before its handler, so it is called at most once whatever the number of threads. A false or raising condition does not consume it; a handler that raises does.                                                               | same    | `Subscription._claim`               |
| P10 | Synchronous by default | `trigger_event` never awaits. **If a registration of the snapshot has a coroutine function as handler, it raises `TypeError` before any condition or handler runs.** Any other awaitable result raises `TypeError` after the call. `atrigger_event` awaits one handler at a time. Conditions are synchronous. | changed | `trigger_event`, `reject_awaitable` |

### Errors, payload, threads

| #   | Property                | Statement                                                                                                                                                                                                                                                                                                 | Status | Enforced by                        |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ---------------------------------- |
| P11 | Fail-fast, never masked | An exception of a handler or a condition propagates unchanged (same object, same type), with a note that names the event and what raised, and the next handlers are skipped. **Nothing that `minevent` does to report it can raise instead of it**: neither adding the note nor naming the callable.      | fixed  | `calls.add_error_note`, `describe` |
| P12 | Bounded messages        | A message of `minevent` is short whatever the size of the user data, and building it never raises because of that data: values are shown with `reprlib`, and a missing key lists at most 20 keys.                                                                                                         | new    | `reprlib`                          |
| P13 | Payload is data         | One read-only `Context` per trigger, shared by the handlers and the conditions, from a mapping with `str` keys or a `Context` used as is. **The keys that are validated are the keys that are stored.** A `Context` can be copied, deep-copied and pickled (protocol 2 or higher). Values are not copied. | fixed  | `Context`                          |
| P14 | Thread-safe registry    | The registry is protected by a reentrant lock. Handlers, conditions, `repr` and finalizers of user objects run outside the lock. This holds with and without the GIL.                                                                                                                                     | same   | `EventManager._lock`               |
| P15 | Exact conditions        | `PeriodicCondition` and `AfterNCondition` count every call once, from any number of threads, and can be copied and pickled.                                                                                                                                                                               | same   | the counter lock                   |
| P16 | Explicit, no state      | No global manager, no discovery, no side effect of a read. A manager is always truthy and cannot be copied or pickled. `repr` shows what is registered. The library logs nothing.                                                                                                                         | same   | `__bool__`, `__reduce__`           |

### Engineering

| #   | Property                   | Statement                                                                                                                                                                                                                                  | Status  | Enforced by         |
| --- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- | ------------------- |
| P17 | Typed                      | Fully typed, `py.typed`, `ty check` clean, no cast and no ignore. A handler argument is typed `Handler`. The values of a `Context` are `Any`.                                                                                              | same    | `ty check`          |
| P18 | Fast and linear            | About 0.3 µs for a trigger with one trivial handler, 0.07 µs for each extra one, 0.8 µs with a small dict, 5.5 µs for a registration plus its removal. A removal is O(1). `get` and `in` of a `Context` cost the same, present or missing. | changed | `tests/benchmarks/` |
| P19 | One home per rule          | One documentation page states each rule; a docstring states what its own object does and names the page or the function that holds the rule.                                                                                               | same    | review              |
| P20 | Checks that mean something | A check fails because the change is wrong, not because the baseline is stale or the checked version is another one: the benchmarks compare with the last run, and the published package is checked with the checks of its own version.     | new     | the workflows       |

Not guaranteed, and documented as such:

- **A removal in another thread** cannot stop a handler whose trigger has already passed the check.
- **Concurrent calls.** A registration without `once` is called by every thread that triggers its
  event, possibly at the same time. The state of a user handler or condition is its own concern.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A hidden coroutine.** A lambda, or a synchronous `functools.wraps` wrapper, that returns a
  coroutine is only detected after its call by `trigger_event`: the handlers before it have run, and
  a `once` registration is consumed.
- **Hidden generators.** A function that returns a generator does nothing.
- **An optional parameter never receives the context.** `def f(context=None)` gets `None`.
- **Names are not checked.** An unbound method `Model.save` is called with the context as `self`.
- **A signature that depends on Python.** `set.add` and `time.sleep` are rejected on 3.11 and 3.12,
  and accepted, then called with the context, from 3.13 [verified].
- **A condition is evaluated by truthiness.** A condition that forgets its `return` is always false.
- **A condition counts its calls, not the triggers.**
- **`StopIteration` in `atrigger_event`** reaches the caller as a `RuntimeError`, because a coroutine
  cannot raise it [verified].
- **A mutable value of the payload** can be mutated by a handler.
- **Delayed release.** A manager with registrations is in a reference cycle; `reset()` releases the
  handlers at a known point.

## 2. Constraints on the target

1. **Simple and easy to maintain.** The package is about 1,500 lines, most of them docstrings. One
   helper is added (`has_kind`), one is replaced (`needs_context` by `adapt_call`), and the flags,
   aliases and lazy-import code that become useless are removed.
2. **Breaking changes are fine.** The README says the API is unstable before 1.0, the last release is
   `0.5.0` and `main` is `0.6.0a0`. No alias and no deprecation period; the changelog follows. The
   future state matters more than the past one: an earlier decision is reversed where it is shown to
   cost the user (D1, D2).
3. **Standard library only** (P2). Plain imports at the top of the modules; `from typing import
TYPE_CHECKING` stays where `ruff` asks for it.
4. **A trigger stays about as fast.** Every added cost is measured and stated (section 6).
5. **Settled decisions without a defect stay**: sequential async, fail-fast, the snapshot, the
   calling rule inferred from the signature (D3), one `Context` per trigger, a truthy and
   non-copyable manager, the benchmarks nightly only, and the non-goals of the design page.

## 3. What differs today

**Baseline on `main`** [verified], Python 3.14.10: `ruff check`, `ruff format --check`, `ty check`
and `inv test.doctest` are clean, 732 unit and integration tests pass with 100% line and branch
coverage, and `pytest tests/benchmarks --benchmark-disable` passes (43 tests). Other interpreters
were used for the probes below, not for the test suite.

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Property | Status     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------- |
| F1  | **A registration removed by its own condition still runs**, but not with `once=True`: the same condition gives `[1]` without `once` and `[]` with it. A condition that calls `reset()` runs its handler too. The page lists the first case as a limit.                                                                                                                                                                                                                           | P8       | [verified] |
| F2  | **`trigger_event` runs half of a trigger for a coroutine handler.** The handlers before it run, then the coroutine function is called, a `once` registration is consumed, and the `TypeError` is raised. All of this is known at registration.                                                                                                                                                                                                                                   | P10      | [verified] |
| F3  | **An async callable object escapes the checks.** An object with `async def __call__` is accepted as a condition and fails at the first trigger, which for `training_end` can be hours later. A callable object whose `__call__` yields is accepted as a handler and silently does nothing. Functions in the same cases are rejected.                                                                                                                                             | P4       | [verified] |
| F4  | **Reporting an error can replace it.** `describe` reads `__qualname__` outside the protection of `add_error_note`: a proxy whose attribute raises turns the `ValueError` of its call into the `RuntimeError` of the attribute.                                                                                                                                                                                                                                                   | P11      | [verified] |
| F5  | **Messages that run or dump user data.** `add_event_handler("e", value)` builds its message with `{value!r}`: a `__repr__` that raises replaces the `TypeError`, and a list of 100,000 items gives a message of 688,924 characters.                                                                                                                                                                                                                                              | P12      | [verified] |
| F6  | **The `KeyError` of a `Context` lists every key**: 118,942 characters and 440 µs for 10,000 keys (a context of metrics or of parameters of a model).                                                                                                                                                                                                                                                                                                                             | P12      | [verified] |
| F7  | **`Context` validates one iteration and stores another.** The keys are checked, then `dict(data)` reads the mapping again: a mapping whose second iteration differs gives `Context({1: 0})`, a non-`str` key. A mapping modified by another thread has the same window [reading].                                                                                                                                                                                                | P13      | [verified] |
| F8  | **The nightly benchmark cannot recover** [reading of the workflow]. It compares with the last **successful** run, which is the one of 2026-11-02. The six runs from 2026-11-20 to 2026-11-25 failed, and the three logs read (11-23 to 11-25) report `get_subscriptions` with 100 handlers 190% to 365% slower. While the step fails, the baseline never moves, so a new regression looks like the old ones, and the results of the failed runs are missing from the next trend. | P20      | [verified] |
| F9  | **The nightly package test checks the published `0.5.0` with the checks of `main`**, which use `Context` and `Subscription`: it cannot pass before a release. The last runs seen were cancelled or queued, so no log confirms it.                                                                                                                                                                                                                                                | P20      | [reading]  |
| F10 | **Code kept for the old import rule.** A module `__getattr__` and `__dir__` read the version lazily, three function-local imports carry `noqa: PLC0415`, and `test_import.py` and `package_checks.py` assert the modules that are absent.                                                                                                                                                                                                                                        | P2       | [reading]  |
| F11 | **Five attributes express two calls.** `Subscription` keeps `_with_context`, `_condition_with_context`, `_handler`/`_handler_call` and `_condition_call`; the flag is tested at each trigger, and `_invoke` exists to hide it.                                                                                                                                                                                                                                                   | P19      | [reading]  |

What is already right and must not regress: callables as handlers and conditions; the calling rule
checked once; one read-only `Context` per trigger; the keyword-only options owned by the
`Subscription`; the atomic `once` claim; the O(1) removal; the release of handlers outside the lock;
the exact built-in conditions; 100% coverage.

## 4. Architecture

```text
add_event_handler(event, handler, *, once, condition)
        |   calls.adapt_call(handler), calls.adapt_call(condition)  -> two callables of (context)
        |   calls.has_kind: reject generators and async conditions, remember an async handler
        v
EventManager._subscriptions                  event -> ordered dict of Subscription, under the lock
        |
trigger_event(event, context) / atrigger_event(event, context)
        |   snapshot under the lock, one Context
        |   trigger_event only: an async handler in the snapshot -> TypeError, nothing has run
        v
for each subscription:
        removed, or guarded and not _claim(context)  -> skip    condition -> still active -> once
        _handler_call(context)
        awaitable result                             -> TypeError (sync) or await (async)
```

The modules and their jobs do not change:

| Module                   | Holds                                                                                                          | Change                          |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `minevent/__init__.py`   | the exports, `__version__`                                                                                     | eager version, no `__getattr__` |
| `minevent/calls.py`      | how user code is called: `Handler`, `adapt_call`, `has_kind`, `describe`, `reject_awaitable`, `add_error_note` | 4.1, 4.2                        |
| `minevent/manager.py`    | `Subscription`, `EventManager`, `_check_event`, `_as_context`                                                  | 4.3                             |
| `minevent/conditions.py` | `Condition`, the counter of `PeriodicCondition` and `AfterNCondition`                                          | none                            |
| `minevent/context.py`    | `Context`                                                                                                      | 4.4                             |

### 4.1 One adapter per callable (P5, F11)

`needs_context(func, name) -> bool` answers a question whose answer every caller turns into the same
branch. `adapt_call(func, name)` returns the branch, already taken:

```python
def adapt_call(func: Callable[..., object], name: str) -> Callable[[Context], object]:
    ...  # the checks and the rule of needs_context, unchanged
    if not required:
        return lambda _context: func()
    if len(required) == 1 and required[0].kind in positional:
        return func
    raise TypeError(msg)
```

`Subscription` keeps the original callables (for `handler`, `condition` and the names) and the two
adapted ones. `_with_context`, `_condition_with_context` and `_invoke` disappear, and the trigger
calls `subscription._handler_call(context)`. A handler with a parameter is called directly, as it is
the adapter; a handler without parameter costs one more frame, visible in a traceback.

### 4.2 The kind of a callable, and its name (P4, P11, F3, F4)

```python
def has_kind(func: Callable[..., object], predicate: Callable[[object], bool]) -> bool:
    while isinstance(func, functools.partial):
        func = func.func
    if predicate(func):
        return True
    # A function or a method has no other code than its own: only an object has a ``__call__``.
    return not inspect.isroutine(func) and predicate(type(func).__call__)
```

It is used three times: generator and async generator functions (rejected), coroutine conditions
(rejected), coroutine handlers (remembered in `Subscription._is_async`). It respects
`inspect.markcoroutinefunction`.

`describe` never raises, and accepts any object:

```python
def describe(func: object) -> str:
    while isinstance(func, functools.partial):
        func = func.func
    with contextlib.suppress(Exception):
        name = getattr(func, "__qualname__", None)
        if isinstance(name, str):
            return name
    return type(func).__qualname__
```

### 4.3 Dispatch (P8, P10, F1, F2)

```python
# Subscription._claim, after the condition
return self.remove() if self._once else self._active


# EventManager.trigger_event
subscriptions = self.get_subscriptions(event)
context = _as_context(context)
for subscription in subscriptions:
    if subscription._is_async:
        name = describe(subscription.handler)
        msg = f"{name} is a coroutine function; use atrigger_event for the event {event!r}"
        raise TypeError(msg)
for subscription in subscriptions:
    ...  # the loop of today, with _handler_call
```

The first loop rejects the trigger as a whole, whatever the conditions would answer: the same call
fails the same way at the first trigger, not at the first epoch where a condition is true. The check
of the result stays, for the coroutines that only the call can reveal.

### 4.4 Messages and `Context` (P12, P13, F5 to F7)

```python
msg = f"handler must be callable, but got {reprlib.repr(handler)}"  # the same for condition

_KEYS_REPR = reprlib.Repr()
_KEYS_REPR.maxlist = 20


class Context(Mapping[str, Any]):
    def __init__(self, data: Mapping[str, object] | None = None) -> None:
        ...  # the type check of today
        copy = {} if data is None else dict(data)
        for key in copy:  # the copy is checked, not the argument
            if not isinstance(key, str):
                msg = f"the keys of data must be str, but got {reprlib.repr(key)}"
                raise TypeError(msg)
        self._data = copy

    def __getitem__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError:
            keys = _KEYS_REPR.repr(list(self._data))
            msg = f"key {reprlib.repr(key)} not found in the context; available keys: {keys}"
            raise KeyError(msg) from None
```

`get` and `__contains__` keep their direct reads: building a bounded message still costs
microseconds.

### 4.5 Plain imports (P2, F10)

`inspect` and `annotationlib` (under `sys.version_info >= (3, 14)`) are imported at the top of
`calls.py`, `inspect` and `reprlib` at the top of `manager.py`, and the `typing` names that are used
move out of the `TYPE_CHECKING` blocks. The package `__init__` loses `__getattr__` and `__dir__`:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # the package is not installed
    __version__ = "0.0.0"
```

No use is added for `logging` or `asyncio`: the library logs nothing and needs only `await`. The
lazy-module checks of `test_import.py` and `package_checks.py` are deleted, and the line of
`CLAUDE.md` that asks for lazy heavy imports becomes "import the standard library at the top of the
module".

### 4.6 Workflows (P20, F8, F9)

- `ci-benchmark.yaml` and `ci-benchmark-import.yaml` take the baseline from the last run of `main`
  that **finished** (success or failure), not the last successful one. A regression then fails one
  night, with its name, and the next night compares with it. Both compare the median (the import
  benchmark compares the mean today).

  ```bash
  gh run list --workflow ci-benchmark.yaml --branch main --limit 20 --json databaseId,conclusion \
    --jq '[.[] | select(.conclusion == "success" or .conclusion == "failure")][0].databaseId'
  ```

- `nightly-test-package.yaml` checks out `tests/package_checks.py` of the tag `v<installed version>`
  after the installation, so each published version is checked with its own checks.

## 5. Public API after the change

The names and signatures of `minevent` do not change.

```text
from minevent import (
    AfterNCondition,  # (n)
    Condition,  # Callable[[], bool] | Callable[[Context], bool]
    Context,  # Mapping[str, Any]
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
len(manager), event in manager, bool(manager)

subscription.event, .handler, .once, .condition, .active
subscription.remove()  # bool
with subscription: ...  # removed on exit
```

### Migration

| Before                                                           | After                                                             |
| ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| a condition that removes its own registration, and the call runs | the handler does not run                                          |
| `trigger_event` with a coroutine handler: earlier handlers run   | `TypeError` before anything runs, also if its condition is false  |
| `... returned an awaitable; use atrigger_event` (with a note)    | for a coroutine function: `... is a coroutine function; use ...`  |
| an object with `async def __call__` as a condition               | `TypeError` at registration                                       |
| a callable object whose `__call__` yields                        | `TypeError` at registration                                       |
| the full `repr` of a value or the full list of keys in a message | shortened by `reprlib`; at most 20 keys                           |
| `minevent.calls.needs_context(f, name)`                          | `minevent.calls.adapt_call(f, name)` (not exported by `minevent`) |
| `__version__` read at the first access                           | read at import                                                    |

Only the first two rows change what a working program does; the others change an error, an internal
helper or the moment of a read.

## 6. Evidence: a prototype

A prototype of 4.1 to 4.5 on a scratch copy of `main`. It has no final docstrings and no new tests;
4.6 was not prototyped.

**Behaviour** [verified]:

| Probe                                                | `main`                      | Prototype                      |
| ---------------------------------------------------- | --------------------------- | ------------------------------ |
| a condition removes its registration                 | runs (`once`: does not run) | does not run                   |
| `trigger_event`, one handler then a `once` coroutine | first runs, `once` consumed | nothing runs, `once` kept      |
| async callable object as condition, and a `partial`  | registered                  | `TypeError`                    |
| callable object that yields, as handler              | registered                  | `TypeError`                    |
| proxy whose `__qualname__` raises, call raises       | the error of the attribute  | the error of the call, a note  |
| non-callable whose `__repr__` raises                 | the error of `__repr__`     | `TypeError`                    |
| missing key, 10,000 keys: length of the message      | 118,942                     | 248                            |
| mapping that changes between two iterations          | a non-`str` key is stored   | the copy is checked and stored |

The probes of these rows give the same results with the prototype on 3.11, 3.12, 3.13, 3.14, 3.14t
and 3.15.

**Existing tests** [verified, 3.14]: `ruff check`, `ruff format --check` and `ty check` are clean on
`src` (the version with the `typing` names moved had one import-order report of `ruff`, fixable
automatically). Without `test_calls.py` (it imports `needs_context`): 630 pass and 20 fail. With a
shim for `needs_context`, the 82 tests of `test_calls.py` pass. The 20 failures are the tests of
what changes: `Subscription._invoke` (8), the awaitable messages and the async callable objects (7),
the lazy version and `dir` (4), and the lazy-import check of `package_checks.py` (1).

**Speed** (Python 3.14.10, µs, best of 15 repetitions, three runs that agree) [verified]:

| Case                                 | `main` | Prototype |
| ------------------------------------ | -----: | --------: |
| trigger, no handler                  |   0.19 |      0.21 |
| trigger, 1 handler without parameter |   0.28 |      0.31 |
| trigger, 10 handlers, no parameter   |   0.82 |      0.90 |
| trigger, 1 handler with the context  |   0.29 |      0.29 |
| trigger, 10 handlers with context    |   0.83 |      0.72 |
| trigger, 1 handler, dict             |   0.75 |      0.78 |
| trigger, 1 handler, condition        |   0.37 |      0.40 |
| registration plus removal            |    4.4 |       5.6 |
| registration plus removal, condition |    8.7 |      10.4 |
| `context[key]` missing, 1 key        |    0.5 |       1.7 |
| `context[key]` missing, 100 keys     |    5.0 |       8.4 |
| `context[key]` missing, 10,000 keys  |    438 |        43 |

Accepted costs: the pre-pass and the adapter add 0.02 to 0.03 µs to a small trigger, and 0.008 µs per
handler without parameter (a handler with the context is 0.01 µs faster); a registration costs 1.2 to
1.8 µs more for the checks of `has_kind`; a missing key of a small context costs more to format with
`reprlib` (a large one costs ten times less, and it is the path of an error).

**Import** [verified]: `import minevent` goes from about 5 ms and 25 new modules to about 25 ms or
more and 118 new modules, almost all of it for `importlib.metadata` and the version read (D2).

Not verified: the speed on other versions, the test suite on other versions, Linux and Windows.

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own, stacked where it says
so. Each step updates the docstrings, `architecture.md`, `design.md`, the guide and the changelog
for what it changes.

| Step | Branch                                    | Change                                                                                             | Breaking | Fixes  | Pull request |
| ---- | ----------------------------------------- | -------------------------------------------------------------------------------------------------- | -------- | ------ | ------------ |
| 1    | `bugfix/skip-removed-by-condition`        | The return of `_claim` (4.3)                                                                       | **yes**  | F1     |              |
| 2    | `bugfix/keep-the-error-of-the-user`       | `describe` never raises (4.2)                                                                      | no       | F4     |              |
| 3    | `bugfix/shorten-error-messages`           | `reprlib` in the messages of the manager and of `Context` (4.4)                                    | messages | F5, F6 |              |
| 4    | `bugfix/check-copied-context-keys`        | Validate the copy (4.4), on 3                                                                      | no       | F7     |              |
| 5    | `refactor/import-stdlib-at-top`           | 4.5: eager version, delete the lazy checks, `CLAUDE.md`, the "cheap import" entry of the changelog | no       | F10    |              |
| 6    | `refactor/adapt-calls` (on 5)             | `adapt_call` (4.1)                                                                                 | internal | F11    |              |
| 7    | `feat/detect-async-callables` (on 6)      | `has_kind` for the generators and the conditions (4.2)                                             | **yes**  | F3     |              |
| 8    | `feat/reject-async-handlers-early` (on 7) | The pre-pass of `trigger_event` (4.3), a benchmark                                                 | **yes**  | F2     |              |
| 9    | `ci/fix-benchmark-baseline`               | The baseline and the median (4.6), `GUIDELINES.md`                                                 | no       | F8     |              |
| 10   | `ci/check-published-package`              | The checks of the installed version (4.6), `GUIDELINES.md`                                         | no       | F9     |              |

Order of value if only part is taken: **9** (without it no later cost or regression can be seen),
then **1, 7 and 8** (a program does something other than what was asked), then **2 to 4** (the errors),
then **5, 6 and 10**. Steps 1, 2, 3, 5, 9 and 10 are independent.

## 8. Tests and gates

Unit tests mirror the source tree; the rules of `CLAUDE.md` apply (one behaviour per test, `match` on
every `pytest.raises`, literals for expected values, a regression test that fails on `main`).

| Test                                                             | Behaviour                                                           | Step |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- | ---- |
| `test_claim_condition_removes_registration` (parametrized)       | `False` with and without `once`                                     | 1    |
| `test_trigger_event_condition_resets_manager`                    | the handler is not called                                           | 1    |
| `test_describe_qualname_raises`, `..._not_a_str`                 | the name of the class                                               | 2    |
| `test_trigger_event_keeps_error_of_unnameable_handler`           | the exception of the call and its note                              | 2    |
| `test_add_event_handler_not_callable_repr_raises` (parametrized) | `TypeError` for handler and condition                               | 3    |
| `test_context_getitem_many_keys`                                 | the whole message as one literal                                    | 3    |
| `test_context_validates_the_copy`                                | a mapping that changes between iterations is rejected or consistent | 4    |
| `test_version_fallback_without_metadata` (integration)           | `python -S` with `src` on the path reads `0.0.0`, no patch          | 5    |
| `test_adapt_call` (parametrized)                                 | returns `func` itself, or calls it without argument                 | 6    |
| `test_has_kind` (parametrized)                                   | function, method, partial, object, class, marked function           | 7    |
| `test_add_event_handler_async_callable_condition`                | `TypeError`, manager unchanged                                      | 7    |
| `test_trigger_event_async_handler_runs_nothing`                  | no handler and no condition is called                               | 8    |
| `test_trigger_event_async_handler_keeps_once`                    | the registration is still active                                    | 8    |
| `test_trigger_event_hidden_coroutine` (kept)                     | a lambda that returns a coroutine raises after the call             | 8    |

Gates before each merge: `ruff check src tests`, `ruff format src tests`, `ty check`,
`pytest tests/unit tests/integration --cov=minevent --cov-branch` at 100%, `inv test.doctest`,
`python tests/package_checks.py`, and a local comparison of the benchmarks with `main` for steps 6
to 8 (the benchmarks stay nightly only in CI). Steps 9 and 10 are checked with `actionlint` and a
manual run of the workflow, which a pull request cannot prove.

## 9. Decisions for the maintainers

- **D1. Reject a coroutine handler before the trigger runs?** _Recommended: yes._ It reverses the
  earlier "no". A partial trigger with a consumed `once` is hard to recover from, and the cost is one
  loop over the snapshot. It also rejects a coroutine handler whose condition would be false, which
  is a program that fails later. Alternative: check inside the loop before the claim; it keeps the
  `once` registration but still runs the earlier handlers.
- **D2. Read the version at import?** _Recommended: yes_, as P2 allows it: 15 lines, two dunder
  functions and four tests go away. The cost is real, about 20 ms on the first import. If a program
  imports `minevent` in many short processes, keep the module `__getattr__` and apply the rest of
  4.5.
- **D3. Replace the calling rule by one shape, `f(context)`?** _Recommended: no._ It would remove the
  signature inspection (the 18 statements of `needs_context`), the differences between Python
  versions and the optional-parameter surprise. But `model.train` and `lambda: ...` could no longer
  be registered as they are, and a wrong signature would be found at the trigger instead of at
  registration. The rule has one home and the adapter of 4.1 keeps its cost away from the dispatch.
- **D4. Require a condition to return a `bool`?** _Recommended: no._ It would catch the forgotten
  `return`, and reject the booleans of NumPy and the usual truthy tests.
- **D5. Return a tuple from `events`, like `get_subscriptions`?** _Recommended: no._ It fixes
  nothing.
- **D6. Give `Context` a `__reduce__`** to pickle with the protocols 0 and 1? _Recommended: no._
  Rebuilding from the arguments would break the deep copy of a context that holds itself.
- **D7. Log with `logging`,** now that its import is allowed? _Recommended: no._ P16: the traceback,
  the note and the `repr` are enough, and tracing is a three-line wrapper.

## 10. Not covered

- **The non-goals of the design page** (event objects, priorities, wildcards, weak references,
  collected errors, concurrent dispatch): unchanged.
- **Return values of handlers**: `trigger_event` returns `None`.
- **Typed payloads** (a `TypedDict` per event): needs its own design if users ask.
- **A name for lambdas** in notes and `repr` (the file and the line): the traceback has them.
- **Other type checkers**: only `ty` is used.
- **Releasing `0.6.0`**: better after this plan, so the release does not publish behaviour that
  changes again.
- **`review/context_object_design.md`**: a past proposal, left as it is.

---

## Appendix: effect on the size of the package

| Item                    |      Today |  Prototype | Why                                                     |
| ----------------------- | ---------: | ---------: | ------------------------------------------------------- |
| `__init__.py` (lines)   |         68 |         53 | no `__getattr__`, no `__dir__`                          |
| `calls.py` (lines)      |        198 |       ~220 | `has_kind` (a final docstring adds about 25 lines)      |
| `manager.py` (lines)    |        821 |       ~790 | no flags, no `_invoke`; the pre-pass                    |
| `context.py` (lines)    |        136 |       ~140 | bounded message                                         |
| `conditions.py` (lines) |        295 |        295 | unchanged                                               |
| `src` statements        |        373 |        381 | the new checks cost a little more than the removed code |
| exported names          | 7, version | 7, version |                                                         |
| runtime dependencies    |          0 |          0 |                                                         |

The prototype has no final docstrings, so the line counts will differ; the gate is the behaviour
(sections 1 and 8), not the size.
