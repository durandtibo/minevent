# `minevent`: target state and the changes to reach it

This document describes the design that `minevent` should have, then the changes to make to the
current implementation (`main`, `3b67360`, #862) to get there. The design follows the properties of
the architecture page (`docs/docs/architecture.md`) and the rules of `CLAUDE.md`. It replaces the
previous version, whose steps are on `main` (#851 to #857, #860, #861) or were declined (#859).

The aim in one line: **what the package states is true on every supported Python, and an error says
what failed.** The design stays: an event is a string, a handler is a callable, the manager connects
them, the `Subscription` is the registration, the `Context` is the payload. No concept is added.
What differs today is at the edges: error notes, threads without the GIL, the cost of reading a
missing key, one condition that cannot express a common schedule, and handler types that a type
checker cannot check.

Items are tagged **[verified]** (reproduced with a script, a test run or a measurement on `main`,
Apple laptop, scripts and prototype kept outside the repository) or **[reading]** (from the code, the
documents or the workflows). This change touches this document only: nothing in `src`, `tests` or
`docs` is modified.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the **target**. Each design choice below exists to make one of them true by
construction. "Status" compares the row with `docs/docs/architecture.md` today: **same**,
**changed** (the statement changes), **fixed** (the statement is already claimed but is not true
today) or **new**.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                                                                                                                | Status  | Enforced by                                            |
| --- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------ |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Seven exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Handler`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.                                | changed | `__all__` and review                                   |
| P2  | Cheap import                 | `import minevent` has no side effect (no thread, file, warning or log), uses the standard library only, imports none of `logging`, `inspect`, `asyncio` and `importlib.metadata`, and creates no `typing` object.                                                                                                                                                                                                                                        | changed | `test_import.py`                                       |
| P3  | Events are strings           | An event name is a case-sensitive `str` (a `StrEnum` member is one, and is kept as given); `add_event_handler`, `on`, `get_subscriptions`, `trigger_event`, `atrigger_event` and `clear_event` raise `TypeError` for another type. `in` answers like a dict (`1 in manager` is `False`). The empty string is valid. Reading the manager never creates an event.                                                                                          | changed | `_check_event`, `test_manager.py`                      |
| P4  | Validated at the door        | `add_event_handler` and `on` reject, with a `TypeError` that names the argument and the value: a non-`str` event, a non-callable handler or condition, a signature that P13 rejects, a generator or async generator function, and **a coroutine function used as a condition**. A rejected registration leaves the manager unchanged. The annotations do not have to be resolvable.                                                                      | changed | `Subscription`, `calls.needs_context`                  |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` until the registration is removed, by whatever means.                                                                                                                                                                                 | same    | `Subscription`, `test_manager.py`                      |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                                                                                                              | same    | the ordered `dict`                                     |
| P7  | Snapshot dispatch            | A trigger visits the registrations that exist when it starts. A registration **added** by a running handler takes effect at the next trigger. A registration **removed** before its turn does not run.                                                                                                                                                                                                                                                   | same    | the dispatch loop                                      |
| P8  | Fail-fast with context       | An exception of a handler or a condition propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and **what raised: the handler, or the condition and its handler**, once per distinct note. **Adding the note never replaces the exception.** No message of the package runs the `repr` of user data to name a callable.                                                                    | fixed   | `calls.add_error_note`, `Subscription._claim`          |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim just before its handler is called, after its condition, so it is called at most once whatever the number of threads. A false or raising condition does not consume it; a handler that raises does.                                                                                                                                                                                                   | same    | `Subscription._claim`, `test_manager_threads.py`       |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError`. `atrigger_event` awaits the handlers one after the other. **Conditions are synchronous in both**: a coroutine function is rejected at registration (P4), and a condition that returns an awaitable raises `TypeError`. A coroutine that is rejected is closed.                                                                                                     | changed | `calls.reject_awaitable`                               |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions, the `repr` and **the finalizers** of user objects run outside the lock, so they can use the manager. This holds with and without the GIL.                                                                                                                                                                                                                                           | fixed   | `EventManager._lock`, `test_manager_threads.py`        |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependency. A manager cannot be copied or pickled.                                                                                                                                                                                                                                                                                                                               | same    | `__reduce__`                                           |
| P13 | Two calls                    | A handler and a condition are called as `f()` or `f(context)`. A parameter that has a default keeps it: the manager never fills it. A callable whose other parameters are none is called as `f()`; one with exactly one other parameter, positional, is called as `f(context)`; any other signature (including `*args` and `**kwargs`), or one that cannot be inspected, is rejected. Names and annotations are not checked. The signature is read once. | same    | `calls.needs_context`                                  |
| P14 | Payload is data              | `trigger_event(event, context=None, /)` copies a mapping with `str` keys, or reuses a `Context` as is, into one read-only `Context` per trigger, shared by the handlers and the conditions. A `Context` can be copied, deep-copied and pickled (protocol 2 or higher) if its values can. The values are not copied.                                                                                                                                      | same    | `Context`, `test_context.py`                           |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean. The values of a `Context` are `Any`. **A handler argument is typed `Handler`**, so a type checker reports a callable that needs two arguments, a keyword-only argument or an argument of another type.                                                                                                                                                                                                        | changed | `ty check`, `test_context_typing.py`                   |
| P16 | Fast and linear              | About 0.3 µs for a trigger with one trivial handler, 0.06 µs for each extra one, 0.75 µs with a small dict, and 4.5 µs for a registration plus its removal. **Reading a value of a `Context` costs the same, present or missing, whatever the number of keys.** Registering _k_ handlers and removing them in any order costs O(_k_). Measured on a laptop with Python 3.14.                                                                             | changed | `tests/benchmarks/`                                    |
| P17 | A manager is a service       | `bool(manager)` is always `True`; `len(manager)` is the number of registrations.                                                                                                                                                                                                                                                                                                                                                                         | same    | `__bool__`                                             |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to adapt a callable (a function, a lambda or a `functools.partial`), one way to run once (`once=True`), one way to extend (write a callable), **one option to shift a period (`start`)**. One page states each rule; a docstring states what its own object does and names the page or the function that holds the rule.                                             | changed | the signatures, the documents                          |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function, `repr(manager)` counts the registrations per event. The library logs nothing.                                                                                                                                                                                                                                                                                                             | same    | `__repr__`                                             |
| P20 | Everything that runs, is run | Each pull request runs the unit and integration tests, the doctests, `tests/package_checks.py` and one pass of **every** benchmark. A test passes or fails for the same reason on every Python of the matrix, with and without the GIL.                                                                                                                                                                                                                  | changed | CI                                                     |
| P21 | Exact built-in conditions    | `PeriodicCondition` and `AfterNCondition` count every call once, from any number of threads, with and without the GIL. They can be copied and pickled.                                                                                                                                                                                                                                                                                                   | new     | a lock in the conditions, `test_conditions_threads.py` |

Not guaranteed, and documented as such:

- **A removal in another thread.** P7 is exact in the thread that triggers. A `remove()` from another
  thread cannot stop a handler that the trigger is about to call.
- **Concurrent calls of one handler.** A registration without `once` is called by every thread that
  triggers its event, possibly at the same time.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A coroutine handler used with `trigger_event`.** The error is raised after the call: the handlers
  before it have run, and a `once` registration is consumed.
- **Generators that are not generator functions.** A callable object whose `__call__` yields, and a
  function that returns a generator, do nothing.
- **An optional parameter never receives the context.** `def f(context=None)` gets `None`.
- **A signature that depends on Python.** The rule reads what `inspect.signature` reports, and the
  standard library adds signatures to C callables between versions: `set.add` and `time.time` are
  rejected on 3.11 and 3.12, and accepted on 3.13 and later [verified].
- **A condition counts its calls, not the triggers.** It is not called when an earlier handler
  raised, nor for a removed registration.
- **The state of a user condition** under threads. Only the built-in ones are protected (P21).
- **A mutable value of the payload** can be mutated by a handler, and the next ones see it.
- **Prompt reclamation.** A manager with registrations is in a reference cycle; `reset()` releases
  the handlers at a known point.

## 2. Constraints on the target

1. **Simple and easy to maintain.** The only new names are `Handler` (a type alias) and the module
   `minevent.calls`. One option replaces another (`start` for `skip_first`). Code is added where a
   statement of section 1 is not true, and removed where it is written twice.
2. **Breaking changes are fine** (the README says the API is unstable before 1.0, the last release is
   `0.5.0`, and neither `skip_first`, `Subscription` nor `Context` is in it). No alias and no
   deprecation period; the changelog follows.
3. **A trigger of a handler without condition is not slower.** A cost added elsewhere is measured and
   stated (section 6).
4. **No dependency**, standard library only, heavy imports lazy.
5. **Settled decisions stay settled** unless a defect is shown: sequential async, fail-fast, the
   snapshot, the calling rule inferred from the signature (defaults kept, `*args` rejected),
   synchronous conditions, one `Context` per trigger, a truthy and non-copyable manager,
   `from typing import TYPE_CHECKING` (#859), and the non-goals of the architecture page.

## 3. What differs today

**Baseline on `main`** [verified], Python 3.14.10: `ruff check`, `ruff format --check`, `ty check`,
`inv test.doctest` and `python tests/package_checks.py` are clean; 584 unit and integration tests
pass in 1.1 s with 100% line and branch coverage. Same tests on other interpreters: 579 pass and 5
are skipped on 3.11, 3.12 and 3.13; 584 pass on 3.15; **one fails on the free-threaded 3.14** (F5).
`pytest tests/benchmarks --benchmark-disable` fails 2 of 35 (F11).

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                              | Property | Status     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------- |
| F1  | **The note blames the handler for the error of a condition.** With `condition=is_late` raising a `KeyError`, the note says `raised by log_epoch while handling the event 'e'`, although `log_epoch` was never called. The same note is added to the `TypeError` of an awaitable condition. The troubleshooting of an error starts in the wrong function.                                                             | P8       | [verified] |
| F2  | **An async condition is accepted at registration** (`async def`, or a `partial` of one) and raises at the first trigger, which for `training_end` can be hours later. The function is detectable at registration.                                                                                                                                                                                                    | P4, P10  | [verified] |
| F3  | **The note can replace the exception.** An exception that is a `frozen=True` dataclass becomes a `FrozenInstanceError`; an exception whose `__notes__` is a tuple becomes `TypeError: Cannot add note`. The first case is listed as a limit, which contradicts "propagates unchanged".                                                                                                                               | P8       | [verified] |
| F4  | **The built-in conditions lose calls without the GIL.** 8 threads calling one condition 200,000 times each on 3.14t: `PeriodicCondition` counted 383,817 of 1,600,000 calls, `AfterNCondition` 372,839. With the GIL no call was lost in the same probe. The free-threaded builds are in the CI matrix.                                                                                                              | P21      | [verified] |
| F5  | **A thread test asserts more than the package guarantees.** `test_remove_from_threads_while_triggering` expects each handler to run at most once, with several threads triggering registrations that are not `once`. It failed in 6 of 10 runs on 3.14t, and passed 10 of 10 with `once=True`. It passes with the GIL because the threads rarely overlap.                                                            | P20      | [verified] |
| F6  | **Reading a missing key of a `Context` is O(keys).** `Mapping.get` and `in` go through `__getitem__`, which builds the error message with the list of the keys, then discards it. With 100 keys, `context.get("missing")` takes 4.5 µs (a dict: 0.017 µs); with 1,000 keys, 40 µs. `context.get(key, default)` is the documented way to read an optional value.                                                      | P16      | [verified] |
| F7  | **`PeriodicCondition` cannot fire on every Nth call.** With `freq=3` it is true on the calls 1, 4, 7, or 4, 7, 10 with `skip_first=True`. "At the end of every third epoch" (calls 3, 6, 9) needs a user condition.                                                                                                                                                                                                  | P18      | [verified] |
| F8  | **A wrong signature is invisible to a type checker.** `handler` is `Callable[..., object]`, so `def f(a, b)` is only reported at run time.                                                                                                                                                                                                                                                                           | P15      | [reading]  |
| F9  | **Finalizers can run under the lock.** `clear_event` and `reset` release the removed handlers inside the `with self._lock` block. A `__del__` that waits for another thread using the manager blocks: reproduced with `clear_event` and two handlers; `reset` has the same structure with two events [reading].                                                                                                      | P11      | [verified] |
| F10 | **Statements that are not true.** The guide advises "constants or an `Enum` with `str` values": a plain `Enum` member is rejected (only a `str` subclass such as `StrEnum` works). P1 says it is enforced by `test_init.py`, which tests `__version__` and `dir` only. P3 says another type raises `TypeError`, and `1 in manager` returns `False`. `dir(minevent)` lists `__version__` twice once it has been read. | P1, P3   | [verified] |
| F11 | **`--benchmark-disable` does not run every benchmark.** The two import benchmarks fail (`min()` of an empty list), so CI ignores the file, and `conftest.py` says the option runs each benchmark once.                                                                                                                                                                                                               | P20      | [verified] |
| F12 | **The rules are written many times.** `manager.py` has 1,032 lines, 727 of them in docstrings (70%). The calling rule is restated in `_needs_context`, `Subscription`, `_call`, `EventManager`, `add_event_handler`, `trigger_event` and the docstring of `conditions`. A change of the rule edits all of them. `test_manager.py` has 2,396 lines and mixes the calling rule, the notes, `Subscription` and manager. | P18      | [verified] |

What is already right and must not regress: callables as handlers and conditions; the calling rule
checked once; one read-only `Context` per trigger; the keyword-only options owned by the
`Subscription`; the atomic `once` claim after the condition; a removed registration never starts;
the O(1) removal; the lazy `inspect` and `__version__`; 100% coverage.

## 4. Architecture

```text
add_event_handler(event, handler, *, once, condition)
        |   Subscription: calls.needs_context (handler, condition), reject an async condition
        v
EventManager._subscriptions                  event -> ordered dict of Subscription, under the lock
        |
trigger_event(event, context) / atrigger_event(event, context)
        |   snapshot under the lock, one Context
        v
for each subscription:
        inactive, or guarded and not _claim(context)  -> skip   condition -> once claim
        _invoke(context)                              -> handler() or handler(context)
        awaitable result                              -> TypeError (sync) or await (async)

an error of the condition: note "the condition c of h"      an error of the handler: note "h"
```

| Module                   | Holds                                                                                                 | Change |
| ------------------------ | ----------------------------------------------------------------------------------------------------- | ------ |
| `minevent/calls.py`      | how user code is called: `Handler`, `needs_context`, `describe`, `reject_awaitable`, `add_error_note` | new    |
| `minevent/manager.py`    | `Subscription`, `EventManager`, and their helpers `_check_event`, `_as_context`                       | less   |
| `minevent/conditions.py` | `Condition`, the counter shared by `PeriodicCondition` and `AfterNCondition`                          | locked |
| `minevent/context.py`    | `Context`                                                                                             | reads  |

The four helpers of `calls.py` are public functions with their own tests (`CLAUDE.md`: shared helpers
are not private functions imported across modules). They are not exported by `minevent`; only
`Handler` is.

### 4.1 The dispatch loop (P8, P10)

Today `Subscription._call` evaluates the condition and calls the handler, and returns `None` both for
"skipped" and for "the handler returned `None`". The manager cannot know which of the two raised
(F1). The target splits the two stages:

```python
# Subscription
def _claim(self, context: Context) -> bool:
    if self._condition is not None:
        try:
            result = (
                self._condition_call(context)
                if self._condition_with_context
                else self._condition_call()
            )
            if result is not True and result is not False:
                msg = f"condition {describe(self._condition)} returned an awaitable"
                reject_awaitable(result, msg)
            if not result:
                return False
        except Exception as exc:
            source = f"the condition {describe(self._condition)} of {describe(self._handler)}"
            add_error_note(exc, source, self._event)
            raise
    return not self._once or self.remove()


def _invoke(self, context: Context) -> object:
    return self._handler(context) if self._with_context else self._handler()


# EventManager.trigger_event
for subscription in subscriptions:
    if not subscription._active or (subscription._guarded and not subscription._claim(context)):
        continue
    try:
        result = subscription._invoke(context)
        if result is not None and isinstance(result, Awaitable):
            msg = f"{describe(subscription.handler)} returned an awaitable; use atrigger_event"
            reject_awaitable(result, msg)
    except Exception as exc:
        add_error_note(exc, describe(subscription.handler), event)
        raise
```

`atrigger_event` is the same loop with `await result` in place of the rejection. `_guarded` is
`once or condition is not None`, computed once. It is there for speed: calling two methods per
handler without it made a trigger of 10 handlers about a third slower than `main` [verified].
`reject_awaitable` closes a coroutine and raises; it replaces the two copies of that code.

### 4.2 The notes never replace the exception (P8)

```python
def add_error_note(exc: Exception, source: str, event: str) -> None:
    note = f"raised by {source} while handling the event {event!r}"
    with contextlib.suppress(Exception):  # a frozen exception, or odd __notes__
        if note not in getattr(exc, "__notes__", ()):
            exc.add_note(note)
```

The note of a handler keeps its text. The note of a condition is
`raised by the condition is_late of log_epoch while handling the event 'epoch_end'`. When the note
cannot be added, the exception propagates without it, which is the lesser loss. `contextlib` is
imported at the top of the module: the maintainers decided during step 5 that P2 does not cover the
light modules of the standard library (and `typing` imports `contextlib` before Python 3.13).

### 4.3 An async condition is rejected at registration (P4, P10)

`Subscription` rejects a condition for which `inspect.iscoroutinefunction` is true (an `async def`
function or method, or a `partial` of one, also on 3.11 [verified]) with
`TypeError: condition must be synchronous, but got never`. The check of the result stays for what
only the call can tell: an object with `async def __call__`, or a lambda that returns a coroutine.

### 4.4 Exact conditions, with one counter (P21, F4, F7)

```python
class _CountingCondition:
    def __init__(self) -> None:
        self._step = 0
        self._lock = threading.Lock()

    def __getstate__(self) -> dict[str, object]:  # a lock cannot be copied or pickled
        return {key: value for key, value in self.__dict__.items() if key != "_lock"}

    def __setstate__(self, state: dict[str, object]) -> None:
        self.__dict__.update(state)
        self._lock = threading.Lock()

    def _next_step(self) -> int:
        with self._lock:
            step = self._step
            self._step = step + 1
        return step

    def reset(self) -> None:
        with self._lock:
            self._step = 0


class PeriodicCondition(_CountingCondition):  # (freq, *, start=0)
    def __call__(self) -> bool:
        offset = self._next_step() - self._start
        return offset >= 0 and offset % self._freq == 0


class AfterNCondition(_CountingCondition):  # (n)
    def __call__(self) -> bool:
        return self._next_step() >= self._n
```

`start` is the index (from 0) of the first call that is true; then one call in `freq` is. It
replaces `skip_first`, which could only express `start=freq` (D1):

| `freq=3`            | True on the calls (from 0) |
| ------------------- | -------------------------- |
| `start=0` (default) | 0, 3, 6, 9                 |
| `start=3`           | 3, 6, 9 (`skip_first`)     |
| `start=2`           | 2, 5, 8 (new: every third) |

`start` is validated like `freq` (an `int`, not a `bool`, at least 0).

### 4.5 Reading a `Context` (P16, F6)

```python
def __contains__(self, key: object) -> bool:
    return key in self._data


def get(self, key: object, default: object = None) -> Any:
    return self._data.get(key, default)
```

Two methods delegate to the dict, so only `context[key]` builds the message of a missing key. `key`
is typed `object` because `ty` rejects `str` as an incompatible override of `Mapping.get`
[verified].

### 4.6 The `Handler` type (P15)

```python
Handler = Callable[[], object] | Callable[[Context], object]
"""A handler: a function without parameter or with the ``Context`` of the trigger."""
```

It is the type of `add_event_handler(handler=...)`, of `Subscription.handler`, and the bound of the
type variable of `on`, so a decorated function keeps its own type. Checked with `ty` on a sample
[verified]:

| Accepted                                                               | Reported                                   |
| ---------------------------------------------------------------------- | ------------------------------------------ |
| `def f()`, `def f(context: Context)`, `async def`, a bound method      | `def f(a, b)`                              |
| `def f(context, verbose=False)`, a method with only defaults           | `def f(*, epoch)`                          |
| `lambda i=i: ...`, `lambda context, i=i: ...`, `partial(save, "p")`    | `def f(context: dict[str, Any])`           |
| a callable object, `[].append`                                         | `def f(epoch: int)`                        |
| `print` (a type checker accepts it; the registration still rejects it) | `@manager.on("e")` on a two-argument `def` |

The run-time check stays the authority (P13).

### 4.7 Release outside the lock (P11)

```python
def clear_event(self, event: str) -> None:
    _check_event(event)
    with self._lock:
        removed = self._subscriptions.pop(event, {})
        for subscription in removed:
            subscription._active = False
    # ``removed`` is released here, without the lock.
```

`reset` swaps the registry for an empty dict in the same way.

### 4.8 One home per rule (P18, F12)

| Where                             | Holds                                                              |
| --------------------------------- | ------------------------------------------------------------------ |
| `architecture.md`                 | the properties, the limits, the calling-rule table, the design     |
| `calls.needs_context` (docstring) | the calling rule, for the readers of the code                      |
| `add_event_handler` (docstring)   | what a user needs at the call: the two shapes, the options, errors |
| other docstrings                  | `Args:`, `Returns:`, `Raises:`, one example; a name, not a copy    |

No documentation page is added or removed. A docstring that repeats the rule is cut to one sentence.

## 5. Public API after the change

```text
from minevent import (
    AfterNCondition,  # (n)
    Condition,  # Callable[[], bool] | Callable[[Context], bool]
    Context,  # Mapping[str, Any]
    EventManager,
    Handler,  # new: Callable[[], object] | Callable[[Context], object]
    PeriodicCondition,  # (freq, *, start=0)
    Subscription,
    __version__,
)

manager = EventManager()
manager.events  # list[str]
manager.get_subscriptions(event)  # tuple[Subscription, ...]
manager.add_event_handler(event, handler, *, once=False, condition=None)
manager.on(event, *, once=False, condition=None)  # decorator
manager.trigger_event(event, context=None, /)
await manager.atrigger_event(event, context=None, /)
manager.clear_event(event)
manager.reset()
len(manager), event in manager, bool(manager)  # bool is always True

subscription.event, .handler, .once, .condition, .active
subscription.remove()  # bool
with subscription: ...  # removed on exit
```

### Migration

From `main` to the target. `skip_first` was never released, so a user of `0.5.0` is not affected by
its removal.

| Before                                               | After                                                        |
| ---------------------------------------------------- | ------------------------------------------------------------ |
| `PeriodicCondition(freq=3, skip_first=True)`         | `PeriodicCondition(freq=3, start=3)`                         |
| `condition.skip_first`                               | `condition.start`                                            |
| an `async def` condition (it raised at the trigger)  | it raises at the registration                                |
| a note `raised by <handler>` for a condition error   | `raised by the condition <condition> of <handler>`           |
| a type error in the code of a user (new reports)     | annotate the parameter of a handler `Context` (or `Mapping`) |
| a subclass of `Context` that overrides `__getitem__` | override `get` and `__contains__` too                        |

### What else follows

| Place                     | Change                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------- |
| `docs/docs`               | the properties, `start` in the examples, `StrEnum` in the guide, `Handler` in the reference |
| `README.md`               | nothing                                                                                     |
| `tests/package_checks.py` | nothing: it uses no changed API                                                             |
| `tests/benchmarks/`       | `start` in `test_handler_benchmark.py`; new benchmarks of a missing key and a condition     |
| `.github/`                | `ci-test.yaml` drops `--ignore` for the import benchmarks; `GUIDELINES.md` follows          |
| `CHANGELOG.md`            | the "Unreleased" section, still written against `0.5.0` only                                |

## 6. Evidence: a prototype

A prototype of 4.1 to 4.5 and 4.7 on a scratch copy of `main`. It has no final docstrings, and the
helpers stayed in `manager.py` (the module `calls.py` was not prototyped). `Handler` was checked on
a separate sample.

**Behaviour** [verified]:

| Probe                                            | `main`                     | Prototype                             |
| ------------------------------------------------ | -------------------------- | ------------------------------------- |
| a condition raises                               | note blames the handler    | note names the condition              |
| `async def` condition, and a `partial` of it     | registered                 | `TypeError` (3.11 and 3.14)           |
| a handler raises a frozen dataclass exception    | `FrozenInstanceError`      | the exception of the handler          |
| a finalizer that uses the manager from a thread  | blocks in `clear_event`    | runs freely in `clear_event`, `reset` |
| 1,600,000 calls from 8 threads, 3.14t            | 23 to 24% of calls counted | all counted                           |
| `PeriodicCondition(3, start=2)`                  | not expressible            | 2, 5, 8                               |
| copy and pickle of a condition                   | work                       | work                                  |
| `dir(minevent).count("__version__")`             | 2                          | 1                                     |
| `context["epoch"] + 1` with an annotated handler | clean under `ty`           | clean under `ty`                      |

**Existing tests** [verified]: without `test_import.py` and `test_package_checks.py` (they need an
installed package), and with a placeholder for the removed `_check_not_awaitable` so that
`test_manager.py` imports: 511 pass, 59 fail, 2 teardown errors. The failures are the tests of what
changes: `Subscription._call` (37), `_check_not_awaitable` (7, and the 2 errors), `skip_first` (6),
an async condition that is now rejected at registration (5) and the signature of the note helper (4).

**Speed** (Python 3.14.10, µs, best of 5 runs of 7 repetitions) [verified]:

| Case                                 | `main` | Prototype |
| ------------------------------------ | -----: | --------: |
| trigger, no handler                  |  0.188 |     0.189 |
| trigger, 1 handler                   |  0.316 |     0.284 |
| trigger, 10 handlers                 |  1.110 |     0.818 |
| trigger, 1 handler, dict             |  0.781 |     0.755 |
| trigger, 1 handler, condition        |  0.345 |     0.369 |
| registration plus removal            |   4.35 |      4.41 |
| registration plus removal, condition |   8.06 |      8.75 |
| one call of `PeriodicCondition`      |  0.075 |     0.166 |
| one call of `AfterNCondition`        |  0.057 |     0.135 |
| `context.get`, present key, 100 keys |  0.049 |     0.042 |
| `context.get`, missing key, 100 keys |  4.478 |     0.038 |
| `in`, missing key, 100 keys          |  4.491 |     0.040 |

Three costs are accepted: a trigger with a condition (+0.02 µs), a registration with a condition
(+0.7 µs, the coroutine check) and a call of a built-in condition (+0.08 to 0.09 µs, the lock). A handler
without condition is faster, because a helper call per handler is gone.

**Import** [verified]: `main` loads 23 modules. With `contextlib` imported at the top, the prototype
loads 24 and takes about 0.4 ms more (4.1 to 4.5 ms, median of 60), a cost that was accepted (see
4.2).

Not verified: the speed on 3.11 to 3.13 and on the free-threaded builds, and Linux or Windows.

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own, stacked where it says
so. Each step updates the docstrings, the property it changes in `architecture.md` and the changelog.

| Step | Branch                                      | Change                                                          | Breaking | Fixes    | Pull request |
| ---- | ------------------------------------------- | --------------------------------------------------------------- | -------- | -------- | ------------ |
| 1    | `bugfix/fix-removal-thread-test`            | Assert what P9 guarantees: `once=True` in the test              | no       | F5       | #864         |
| 2    | `bugfix/count-condition-calls-exactly`      | The shared counter and its lock (4.4, without `start`)          | no       | F4       | #865         |
| 3    | `perf/read-missing-context-keys`            | `get` and `__contains__` (4.5), a benchmark                     | no       | F6       | #867         |
| 4    | `refactor/add-calls-module`                 | Move the helpers to `calls.py` and split `test_manager.py`      | no       | F12      | #868         |
| 5    | `bugfix/name-failing-condition` (on 4)      | `_claim`, `_invoke`, the notes (4.1, 4.2)                       | note     | F1, F3   | #869         |
| 6    | `feat/reject-async-conditions` (on 5)       | The check of 4.3                                                | **yes**  | F2       | #870         |
| 7    | `bugfix/release-handlers-outside-lock`      | 4.7                                                             | no       | F9       | #871         |
| 8    | `feat/add-handler-type` (on 4)              | `Handler` (4.6), a typed sample checked by `ty`                 | types    | F8       | #872         |
| 9    | `feat/replace-skip-first-with-start` (on 2) | `start` (4.4)                                                   | **yes**  | F7       | #873         |
| 10   | `test/run-every-benchmark`                  | The import benchmarks work when disabled; CI drops `--ignore`   | no       | F11      | #874         |
| 11   | `docs/state-each-rule-once` (last)          | Short docstrings (4.8), the statements of F10, `dir`, changelog | no       | F10, F12 | #875         |

Step 1 comes first: a test that fails at random hides the result of the other steps. Step 11 contains
the one-line fix of `__dir__`; take it out as its own `bugfix/` pull request if the documentation
waits. If only part is taken, take **1, 2, 3, 5 and 6**: they are the ones where a user gets a wrong
result, a misleading error or an unexpected cost today.

## 8. Tests and gates

Unit tests mirror the source tree; the rules of `CLAUDE.md` apply (one behaviour per test, `match` on
every `pytest.raises`, literals for expected values, a regression test that fails on `main`).

| Test (module)                                                   | Behaviour                                                      |
| --------------------------------------------------------------- | -------------------------------------------------------------- |
| `test_calls.py` (new)                                           | the tests of the moved helpers, one section per function       |
| `test_add_error_note_frozen_exception`                          | the exception is unchanged, no new error                       |
| `test_add_error_note_notes_not_a_list`                          | the same                                                       |
| `test_trigger_event_condition_raises_note_names_condition`      | the whole list of notes, one literal                           |
| `test_atrigger_event_condition_raises_note_names_condition`     | the same through `atrigger_event`                              |
| `test_trigger_event_handler_raises_after_condition_note`        | the note names the handler only                                |
| `test_add_event_handler_async_condition` (parametrized)         | `async def`, method, `partial`: `TypeError`, manager unchanged |
| `test_trigger_event_condition_returns_awaitable` (kept)         | a lambda and an async `__call__` still raise at the trigger    |
| `test_clear_event_releases_handlers_without_lock` (integration) | a finalizer takes the lock from another thread                 |
| `test_reset_releases_handlers_without_lock` (integration)       | the same, with two events                                      |
| `test_conditions_threads.py` (new, integration)                 | the exact number of calls from `run_threads`, on both classes  |
| `test_periodic_condition_call_start` (parametrized)             | the list of results for `start` 0, 2, 3 and beyond `freq`      |
| `test_periodic_condition_invalid_start`                         | `TypeError` and `ValueError`                                   |
| `test_condition_pickle` / `test_condition_deepcopy`             | the same step, an independent counter and lock                 |
| `test_context_get_missing_does_not_format_keys`                 | a patched `__getitem__` is not called                          |
| `test_context_typing.py` (extended)                             | the accepted shapes of 4.6 type check and run                  |

The lock test of step 2 must be shown to fail on `main` with a free-threaded interpreter
(`uv run --python 3.14t`); with the GIL it passes either way, so say so in the pull request.

Gates before each merge: `ruff check src tests`, `ruff format src tests`, `ty check`,
`pytest tests/unit tests/integration --cov=minevent --cov-branch` at 100%, `inv test.doctest`,
`python tests/package_checks.py`, one pass of the benchmarks, the thread tests repeated on 3.14t for
steps 1, 2 and 7, and the benchmarks compared with `main` for steps 2, 3 and 5 (P16).

## 9. Decisions for the maintainers

- **D1. Replace `skip_first` with `start`?** _Recommended: yes._ One integer covers both and the
  schedule that is missing, and `skip_first` was never released. The cost: `start=freq` says less
  than `skip_first=True`. Alternative: keep `skip_first` and
  document `lambda context: (context["epoch"] + 1) % 3 == 0` for "every third".
- **D2. A lock in the built-in conditions?** _Recommended: yes._ The free-threaded builds are tested
  and a lost count is silent. This changes the earlier decision "no lock in the conditions", because
  F4 shows the defect. Alternative: no lock, and state that a condition must be called from one
  thread; it saves 0.09 µs per call.
- **D3. A module `calls.py`?** _Recommended: yes._ The calling rule is one job with the longest
  tests. Alternative: keep one module and only shorten the docstrings; fewer lines move.
- **D4. Export `Handler`?** _Recommended: yes_, it is the twin of `Condition` and a user who writes
  a wrapper needs it. A checker may report code that works at run time (a parameter annotated
  `dict`); that code would receive a `Context`, so the report is right.
- **D5. Reject a coroutine handler in `trigger_event` before any handler runs?** _Recommended: no_
  (as before). It adds a pass over the snapshot to every trigger, for an error that is already loud.
  The partial run is now listed as a limit.
- **D6. Return a tuple from `events`, like `get_subscriptions`?** _Recommended: no._ A break that
  fixes nothing.
- **D7. Validate `once` as a `bool`?** _Recommended: no_ (`CLAUDE.md`: no validator that is one
  `isinstance`). `once="False"` is truthy; the type checker reports it.

## 10. Not covered

- **The non-goals of the architecture page** (event objects, priorities, wildcards, weak references,
  collecting errors) and concurrent async dispatch: unchanged.
- **Return values of handlers**: `trigger_event` returns `None`.
- **Typed payloads** (a `TypedDict` per event): needs its own design if users ask.
- **Other type checkers.** 4.6 was checked with `ty` only.
- **The scheduled benchmark.** The `Benchmark` workflow failed on its last six runs seen (2026-11-20
  to 2026-11-25) [verified]. The log of 2026-11-24 reports "Performance has regressed" on
  `get_subscriptions` and a thread benchmark. It compares very short timings between runners with a
  50% threshold, so noise is a likely cause [reading], not analysed. It needs its own change.
- **The nightly package tests** install the published `0.5.0` and run the checks of `main`, so they
  cannot pass before a release [reading].
- **Releasing `0.6.0`.** A release after this plan avoids publishing an API that changes again.
- **`review/context_object_design.md`**: a past proposal, left as it is.

---

## Appendix: effect on the size of the package

| Item                    |            Today |   Expected after | Why                                  |
| ----------------------- | ---------------: | ---------------: | ------------------------------------ |
| `manager.py` (lines)    |            1,032 |             ~600 | the helpers move, shorter docstrings |
| `calls.py` (lines)      |                0 |             ~200 | the moved helpers                    |
| `conditions.py` (lines) |              230 |             ~250 | the shared counter, pickling         |
| `context.py` (lines)    |               97 |             ~110 | two methods                          |
| `src` statements        |              292 |             ~310 | pickling, `start`, the async check   |
| exported names          | 6, `__version__` | 7, `__version__` | `Handler`                            |
| runtime dependencies    |                0 |                0 |                                      |

The line counts are estimates; the gate is the behaviour (sections 1 and 8), not the size.
