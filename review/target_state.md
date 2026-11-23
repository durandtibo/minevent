# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`73088fa`, 2026-11-23), and proposes the smallest set of changes that makes every property true.
It replaces the fifth version of this review. That version is **merged** (#807 to #810: handlers are
callables, the options are the keyword-only arguments of `add_event_handler` and `on`, the import is
cheap), so this version starts from the result and does not repeat it.

The package is already small: **1,140 lines** (`src`, docstrings included), **235 statements**,
zero dependency, 350 tests, 100% line and branch coverage, `ruff`, `ty` and `inv test.doctest`
green. There is no structural problem left. What is left is **one behaviour that is a trap, one
object that is split in two, and a few places where the code or the documents say less than they
should**:

- `once=True` combined with a `condition` is consumed by the first trigger even if the condition is
  `False`. `once=True, condition=AfterNCondition(2)` **never runs** [verified]. The quickstart needs
  a workaround class of about 20 lines to express "run the first time the condition is true".
- The options of a registration are applied in three places: the `Subscription` stores them, the
  manager reads `subscription._once` (twice, once per dispatch loop), and `_Options`, a private
  `NamedTuple`, exists only to carry three values into the constructor.
- `repr(subscription)` does not say which handler it is, although the user guide tells the reader to
  print `get_subscriptions(event)` to debug. The `TypeError` for an awaitable prints
  `repr(handler)`, which contains the arguments bound by a `functools.partial`, the thing property
  P8 forbids.
- `architecture.md` states the contract of the payload wrongly (P13), and describes the import less
  precisely than it can be.

The target keeps the design (an event is a string, a handler is a callable, the manager connects
them) and **moves each option to the one place that owns it**. Breaking changes are accepted (the
README says the API is unstable before 1.0, and nothing is released since `0.5.0`).

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, one behaviour per test).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.14,
Apple laptop, scripts and a throw-away prototype kept outside the repository) or **[reading]** (from
the code or the documents). Nothing in `src`, `tests` or `docs` was changed by this review.

**Baseline on `main`** [verified]: `ruff check`, `ruff format --check` and `ty check` clean; 350
unit and integration tests pass in 0.5 s with 100% line and branch coverage (`__init__` 17,
`conditions` 51, `manager` 167 statements); `inv test.doctest` exits 0 and checks the 18 markdown
pages; an AST audit of the unit tests finds no `pytest.raises` without `match`; `import minevent`
takes about 6.2 ms (`-X importtime`, median of 5) and loads 26 modules that a bare interpreter does
not.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, and the plain-callable _conditions_. These are the rules. Each design choice
below exists to make one of them true **by construction**. "Status" compares the row with
`docs/docs/architecture.md` today: **same** (wording kept), **changed** (the statement changes) or
**fixed** (the document was wrong). "Enforced by" names the mechanism and the test module.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                      | Status  | Enforced by                                                  |
| --- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------ |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Five exported names and `__version__` (`EventManager`, `Subscription`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`. | same    | `test_init.py`                                               |
| P2  | Cheap import                 | `import minevent` is cheap and has no side effect: standard library only; it imports not `logging`, `inspect`, `asyncio` or `importlib.metadata`, and it **creates no `typing` object** (`NamedTuple`, `Protocol`, `TypeVar`): the annotations are strings and `typing` is read under `TYPE_CHECKING` only. No thread, no file, no warning, no log.                              | changed | `test_import.py` (modules), review rule (`typing` objects)   |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                             | same    | `test_manager.py`                                            |
| P4  | Validated at the door        | A wrong type raises `TypeError` in the call that receives it, with a message that names the argument and the value: the event, the handler (must be callable) and the condition (`None` or callable) of `add_event_handler` and `on`. An invalid registration leaves the manager unchanged.                                                                    | same    | `add_event_handler`, `on`, `test_manager.py`                 |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`. `active` is `True` if and only if the registration is in the manager.                                                                                    | same    | `Subscription`, `test_manager.py`                            |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                    | same    | the ordered `dict`, `test_manager.py`                        |
| P7  | Snapshot dispatch            | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger, except that a `once` registration removed by an earlier handler of the same trigger does not run.                                                                                                     | changed | `get_subscriptions`, `test_manager.py`, `test_manager_once.py` |
| P8  | Fail-fast with context       | An exception of a handler propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and the name of the handler (the function under a `functools.partial`), once per distinct pair. **No message and no `repr` of the package runs the `repr` of user data**: they name the function, never its arguments. | changed | `_describe`, `_add_error_note`, `test_manager.py`            |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim **just before its handler runs**, so it runs at most once whatever the number of threads. A false condition does not consume it (the condition is evaluated first); a handler that raises does consume it.                                                                                                  | changed | `Subscription._call`, `test_manager_once.py`, `test_manager_threads.py` |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop. An object with `async def __call__` is a coroutine handler like a coroutine function.                                          | same    | `_check_not_awaitable`, `test_manager_async.py`              |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                                                                                                                     | same    | `EventManager._lock`, `test_manager_threads.py`              |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependencies. A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`).                                                                                                                                                            | same    | `__reduce__`, `test_manager.py`                              |
| P13 | Payload is data              | `trigger_event(event, /, **payload)` calls every handler as `handler(**payload)`. Any key is allowed (`event`, `self`). Arguments that do not come from the payload are bound with `functools.partial`: the manager has no second mechanism. With `filter_payload=True` only the keys the signature accepts are passed.                                          | fixed   | `trigger_event`, `test_manager.py`                           |
| P14 | Options are per registration | `once`, `condition` and `filter_payload` are keyword-only arguments of `add_event_handler` and `on` (and of the `Subscription` constructor), with the same names, defaults and meaning. A condition is a `Callable[[], bool]` called once per trigger, before the handler. The built-in conditions keep per-instance state and both have `reset()`.              | changed | signatures, `test_manager.py`, `test_conditions.py`          |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                                                                                             | same    | `ty check` in CI                                             |
| P16 | Fast and linear              | A trigger of one handler costs about 0.4 µs, each extra handler about 0.1 µs, a registration plus its removal about 0.8 µs (Python 3.14, laptop). Registering _k_ handlers and removing them in any order costs O(_k_) in total. Benchmarks guard it.                                                                                                          | changed | `tests/benchmarks/`                                          |
| P17 | A manager is a service       | `bool(manager)` is always `True`, empty or not, so `manager or default` means "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                                                                             | same    | `__bool__`, `test_manager.py`                                |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to bind arguments (`functools.partial`), one way to run a handler once (`once=True`, whatever the condition), one way to extend (write a callable). No handler base class.                                                                                                  | changed | the signatures                                               |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function (`Subscription(event='epoch_end', handler='log_epoch')`), `repr(manager)` counts the registrations per event. The library logs nothing: `get_subscriptions(event)` is the way to look.                                                                                                            | new     | `__repr__`, `test_manager.py`                                |

Not guaranteed, and documented as such (unchanged, listed so the target is complete):

- **A handler removed while a trigger is running** still runs in that trigger (P7).
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A handler that returns a generator** does nothing: only awaitables are detected (P10).
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  dict, `Subscription`, manager): `del manager` does not free it until the garbage collector runs
  [verified]. `reset()` releases the handlers at a known point.
- **State of a condition under threads.** The counter of `PeriodicCondition` and `AfterNCondition` is
  not protected: a stateful condition should be triggered from one thread.
- **A keyword bound by `functools.partial` and given again by the payload**: the payload wins.
- **A condition that raises** gets the note of its registration (`raised by <handler> ...`): the
  note names the registration, not the callable that raised.

## 2. Constraints on the target

1. **Simple and easy to maintain.** The change deletes code (a class, a duplicated branch, a
   workaround of the documents) and adds none that is not a test or a docstring.
2. **Breaking changes are fine** and compatibility is not a design input: no alias, no deprecation
   period. The changelog lists them.
3. **No slower than today.** P16 is measured before and after (section 6): the trigger cost must not
   grow by more than noise.
4. **No dependency**, standard library only, heavy imports lazy (`CLAUDE.md`).
5. **Settled decisions stay settled** unless a defect is shown: snapshot dispatch, sequential async,
   fail-fast, `get_subscriptions`, a lock in the manager and none in the conditions, the note
   without `repr`, a dict as an ordered set, the two dispatch loops not shared, a condition without
   the payload, a truthy and non-copyable manager, one module `manager.py`. Section 9 lists the two
   that this review **reopens** and why.

## 3. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | **`once` + `condition` is a trap.** `trigger_event` claims a `once` registration **before** it evaluates the condition. `add_event_handler("e", f, once=True, condition=AfterNCondition(2))` is consumed by the first trigger and `f` never runs: 4 triggers, `calls == []`, `len(manager) == 0` [verified]. Four documents describe the rule (docstring, guide, quickstart, architecture P9) and the quickstart ships a `FirstTrue` class of about 20 lines to work around it. The rule is the one case where two options do not compose. |
| F2  | **The options are applied by three owners.** `Subscription._call` applies the condition and the filter; `trigger_event` and `atrigger_event` each read `subscription._once` and call the manager's private `_remove` (the same two lines twice); `_Options` (a `NamedTuple`, 2 tests, an import of `typing.NamedTuple`) only carries the three values into `Subscription.__init__` [reading].                                                                                                                                  |
| F3  | **`repr(subscription)` hides the handler.** `get_subscriptions("e")` of two handlers prints `(Subscription(event='e'), Subscription(event='e'))` [verified]. The guide's troubleshooting ("My handler does not run: `manager.get_subscriptions("my_event")`") sends the reader to a list that cannot be read.                                                                                                                                                                                                                  |
| F4  | **The awaitable error prints the arguments.** `trigger_event` of `functools.partial(ah, 1)` raises `functools.partial(<function ah at 0x108a65640>, 1) returned an awaitable; use atrigger_event` [verified]. The note of every other error uses `_describe` precisely so that the `repr` of bound data is never run (P8); this message does not.                                                                                                                                                                              |
| F5  | **`architecture.md` is wrong or loose in three places.** P13 says `trigger_event(event, /, payload)` calls `handler(payload)` (the signature is `**payload` and the call is `handler(**payload)`); the performance paragraph of the guide lists `threading`, `functools` and `typing` as the imports, and omits `collections.abc` (read at import for the `Awaitable` check); P16 gives timings that are 30% to 55% above the measured ones (0.5 µs and 0.15 µs against 0.38 µs and 0.1 µs) [verified].                          |
| F6  | **The import creates `typing` objects it does not need.** `NamedTuple` (`_Options`), `Protocol` (`Condition`) and `TypeVar` (`_F`) are built at import, which pulls `annotationlib`, `ast` and `enum` on Python 3.14: 26 modules and 6.2 ms. The same package with the three objects out loads 22 modules in 4.0 ms (-35%) [verified, prototype]. `Condition` is a protocol with one `__call__`, that is `Callable[[], bool]`, the type that P14 already states.                                                               |
| F7  | **Two unit tests test Python, not the package.** `test_subscription_call_condition_combinator_short_circuit` and `..._evaluates_all` check that `lambda: a() and b()` short-circuits and `all([a(), b()])` does not, and one of them loops in the test body (`CLAUDE.md`: no loop). The behaviour belongs to the language; the documents already say it [reading].                                                                                                                                                              |
| F8  | **The documents repeat the semantics instead of pointing at the property.** The rules of `once`, of the notes, of `partial` and of the threads are written again in the docstrings, the guide, the quickstart, the architecture and the FAQ. F1 and F5 are two consequences: a rule changes in one place and the others drift. The properties table has no "enforced by" column.                                                                                                                                              |

What is already right and must not regress: callables as handlers (one way to bind arguments); the
options as keyword-only arguments; `Subscription` as the identity of a registration (and a context
manager); the snapshot; the atomic claim under the lock; the note that names the function and is
deduplicated; no `repr` of the manager's content in the note; the lazy `inspect` and `__version__`;
`bool(manager)`; the non-copyable manager; 100% coverage and one behaviour per test.

Measured and kept (P16, Python 3.14, 500,000 triggers, best of 5):

| Case                         | Time per trigger |
| ---------------------------- | ---------------: |
| no handler                   |         0.246 µs |
| 1 handler                    |         0.378 µs |
| 1 handler with a payload key |         0.489 µs |
| 1 handler and a condition    |         0.402 µs |
| 1 handler, `filter_payload`  |         0.652 µs |
| 10 handlers                  |         1.246 µs |
| add + remove one handler     |         0.777 µs |

The lock and the snapshot are about 0.25 µs of the trigger. A copy-on-write tuple would make the
read lock-free and the removal O(n): the trade is not worth the rewrite (decided, section 9).

## 4. Target design

### 4.1 The `Subscription` owns the options

A `Subscription` is the record of a registration **and** the rule that runs it. Its constructor
takes the options as keyword-only arguments (P14); `_Options` is deleted. `_call` applies the three
options in a fixed order and nothing else needs to know them:

```python
class Subscription:
    def __init__(
        self,
        manager: EventManager,
        event: str,
        handler: Callable[..., object],
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> None:
        self._manager = manager
        self._event = event
        self._handler = handler
        self._once = once
        self._condition = condition
        self._filter_payload = filter_payload
        # The accepted keys are computed once, at registration.
        self._payload_keys = _accepted_keywords(handler) if filter_payload else None

    def _call(self, payload: dict[str, object]) -> object:
        """Run the registration: condition, once claim, payload filter, handler."""
        if self._condition is not None and not self._condition():
            return None  # not consumed: a once registration waits for its condition
        if self._once and not self.remove():
            return None  # lost the claim: removed by another thread or another handler
        if self._payload_keys is not None:
            payload = {k: v for k, v in payload.items() if k in self._payload_keys}
        return self._handler(**payload)
```

Why this order (P9): the condition decides **whether** the handler would run; the claim decides
**who** runs it. The claim is still one `_remove` under the lock, so at most one thread wins, and it
still happens before the handler, so a handler that raises or that triggers its own event is already
removed. A condition evaluated by two threads at once is the documented, unprotected case.

The dispatch loops lose their `once` branch and read no private field of the subscription:

```python
def trigger_event(self, event: str, /, **payload: object) -> None:
    for subscription in self.get_subscriptions(event):
        try:
            _check_not_awaitable(subscription._call(payload), subscription.handler)
        except Exception as exc:
            _add_error_note(exc, event, subscription.handler)
            raise
```

`atrigger_event` is the same loop with the `await` (the two loops stay separate: a sync and an async
body cannot share a function without a wrapper that costs more than the four lines it saves).
`subscription.once` is still a property for the users; the manager does not need it.

### 4.2 `once` is "the first time it runs"

| Registration                                  | Today                                  | Target                                      |
| --------------------------------------------- | -------------------------------------- | ------------------------------------------- |
| `once=True`                                   | runs at the next trigger, then removed | same                                        |
| `once=True`, condition `False`                | **removed, handler not called**        | **kept**, evaluated again at the next trigger |
| `once=True`, condition `True`                 | removed, handler called                | same                                        |
| `once=True`, condition raises                 | removed (claimed first)                | **kept** (the condition runs first)         |
| `once=True`, handler raises                   | removed                                | same                                        |
| `once=True`, removed by an earlier handler    | skipped                                | same (the claim fails)                      |

`once=True, condition=AfterNCondition(2)` now means "run once, on the third trigger". The
`FirstTrue` class of the quickstart (about 20 lines), the paragraph that explains it and the guide
bullet that points to it are deleted. P18 ("one way to run a handler once") becomes true without an
exception.

### 4.3 Messages and `repr` name the function, never the data

```python
def __repr__(self) -> str:
    return f"{type(self).__qualname__}(event={self._event!r}, handler={_describe(self._handler)!r})"


def _check_not_awaitable(result: object, handler: Callable[..., object]) -> None:
    ...
    msg = f"{_describe(handler)} returned an awaitable; use atrigger_event"
```

`_describe` already unwraps nested `functools.partial` and falls back to the class name of a
callable object. The two reprs and the message use it, so P8 holds everywhere (F3, F4). The options
are not in the `repr` (they are properties): a `repr` that grows with every option is a `repr` that
nobody reads.

### 4.4 `Condition` is a type alias, and the import creates no `typing` object

```python
# conditions.py
from collections.abc import Callable

Condition = Callable[[], bool]
"""A condition: any function without argument that returns a boolean."""
```

`from typing import TYPE_CHECKING` stays (a constant), and `Self`, `NoReturn` and the `TypeVar` of
`on` move under `if TYPE_CHECKING:` (the annotations are strings by `from __future__ import
annotations`). Nothing else changes for the user: `condition=...` accepts the same objects, a class
with `__call__(self) -> bool` is still a condition, `Condition` is still exported and importable.
What goes away is the class that nobody could instantiate or `isinstance`-check (`Protocol` was not
`runtime_checkable`) and the 30 lines of its docstring, which move to the module docstring. The
combination rules (`lambda: a() and b()`) stay in the guide, where they are already written.

### 4.5 One home per fact in the documents (F5, F8)

| Fact                                   | Home                                           | Elsewhere                    |
| -------------------------------------- | ---------------------------------------------- | ---------------------------- |
| The rules (P1 to P19), the limits      | `architecture.md` (the table, "Enforced by")   | linked by number (`P9`)      |
| One recipe per task                    | `guide.md`                                     | no restatement of a rule     |
| The tutorial, runnable examples        | `quickstart.md`                                | no restatement of a rule     |
| Signature, arguments, `Raises`         | the docstrings                                 | rendered by `mkdocstrings`   |
| What the package is, how to install    | `README.md`, `index.md`, `get_started.md`      | unchanged                    |

Concretely: fix P13; add the "Enforced by" column; update P2, P7, P8, P9, P14, P16, P18, P19; update
the import and the performance paragraphs of the guide; delete the `once` workaround of the
quickstart and the sentence of the guide that points at it; shorten the `once` text of the
`add_event_handler` docstring to one sentence that cites the rule. The FAQ entry "How do I run a
handler only once?" stays: it is one line.

## 5. Public API after the change

```python
from minevent import (
    EventManager,
    Subscription,
    Condition,  # now Callable[[], bool], not a Protocol class
    PeriodicCondition,
    AfterNCondition,
    __version__,
)

manager = EventManager()
manager.events                      # list[str]
manager.get_subscriptions(event)    # tuple[Subscription, ...]
manager.add_event_handler(event, handler, *, once=False, condition=None, filter_payload=False)
manager.on(event, *, once=False, condition=None, filter_payload=False)    # decorator
manager.trigger_event(event, /, **payload)
await manager.atrigger_event(event, /, **payload)
manager.clear_event(event)
manager.reset()
len(manager), event in manager, bool(manager)             # always True

subscription.event, .handler, .once, .condition, .filter_payload, .active
subscription.remove()               # bool
with subscription: ...              # removed on exit
```

The surface does not grow: five names, eight members. The `Subscription` constructor stays internal
(documented as such); its third argument changes from `options` to three keyword-only arguments.

### Migration

- `once=True` with a `condition`: the registration waits for the first `True`. A program that relied
  on "consumed by the first trigger whatever the condition" (no known use: it never ran the handler
  in the case that differs) must call `subscription.remove()` itself.
- `Condition` is a `Callable[[], bool]` alias. Code that subclassed the protocol explicitly
  (`class C(Condition)`) must drop the base class: a class with `__call__(self) -> bool` is enough.
- `repr(subscription)` and the awaitable `TypeError` change text. A test that matches
  `functools.partial(` in the message must match the function name.
- `Subscription(manager, event, handler, options)` (internal) takes keyword-only options.

## 6. Evidence

The change was prototyped in a scratch copy of `src` and `tests` (not in the repository) and the
existing suite was run against it.

**Behaviour** [verified, prototype]:

| Probe                                                       | `main`                                    | Prototype                                        |
| ----------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------ |
| `once=True` + `AfterNCondition(2)`, 4 triggers              | handler ran 0 times, `len(manager) == 0`  | ran once, `len(manager) == 0`                    |
| `once=True` + a condition that raises                       | registration removed                      | registration kept (`len(manager) == 1`)          |
| `repr(subscription)`                                        | `Subscription(event='e')`                 | `Subscription(event='e', handler='print')`       |
| `trigger_event` of an async `functools.partial(ah, 1)`      | message with `functools.partial(<function ah at 0x...>, 1)` | `ah returned an awaitable; use atrigger_event` |
| payload with the keys `self` and `event`                    | works                                     | works                                            |
| a handler that calls `manager.reset()`                      | the next handler of the snapshot still runs | same                                           |

**Suite against the prototype**: 345 tests pass, **3 fail, and all 3 are the changed behaviours**
(`test_event_manager_add_event_handler_condition_false_consumes_once`,
`test_event_manager_add_event_handler_once_removed_when_condition_false`, and
`test_subscription_repr`). The two `_Options` tests were deleted with the class. The thread tests of
`once` (at-most-once under contention) pass unchanged. `ty check src` passes; `ruff` reports two
fixable issues in the prototype, which were not cleaned (the prototype is not the implementation).

**Size and speed** [verified, prototype]:

| Measure                            | `main` | Prototype |
| ---------------------------------- | -----: | --------: |
| `src` lines                        |  1,140 |     1,089 |
| `import minevent` (ms, median of 3 or more) |   6.2 |       4.0 |
| Modules loaded by the import       |     26 |        22 |
| Trigger of 1 handler (µs)          |  0.378 |     0.395 |
| Trigger of 1 handler + condition   |  0.402 |     0.406 |
| Trigger, 10 handlers               |  1.246 |     1.260 |

The trigger is within noise (the `once` check moved into `_call`; a non-`once` registration pays one
attribute test). The import is 35% faster.

## 7. Changes to reach the target state

One branch and one pull request per step, stacked (`CLAUDE.md`), each mergeable alone and green.

1. **`docs/fix-architecture-properties`**: fix P13 (`**payload`, `handler(**payload)`), the import
   list and the timings of P16 and of the guide. Add the "Enforced by" column (names of the modules
   and mechanisms, no automatic check). No code. Risk: none.
2. **`refactor/subscription-owns-options`**: delete `_Options`; keyword-only options in
   `Subscription.__init__`; `_call` applies the claim; the dispatch loops lose their `once` branch.
   `once` still claims **before** the condition in this step, so **no behaviour changes** and the
   suite is green as it is (two tests of `_Options` removed, the constructor tests updated).
3. **`bugfix/describe-handler-in-repr-and-errors`**: `repr(subscription)` and the awaitable
   `TypeError` use `_describe` (F3, F4). Regression tests: the message of a `partial` has no `repr`
   of the bound data and a handler whose `repr` raises still gives the error.
4. **`feat/once-waits-for-the-condition`** (**breaking**): move the claim after the condition (a
   two-line swap in `_call`); rewrite P7 and P9 and the `once` text of the docstrings; delete the
   `FirstTrue` workaround from the quickstart and the guide bullet; update the two tests of the
   old rule and add the new ones (section 8); changelog entry with the migration.
5. **`refactor/condition-is-an-alias`** (**breaking**, small): `Condition = Callable[[], bool]`,
   `Self`, `NoReturn` and the `TypeVar` under `TYPE_CHECKING`; module docstring of `conditions`;
   test of the import (`typing.Protocol` and friends are not created); P2 and the guide's
   performance paragraph. Measure the import before and after in the description.
6. **`test/remove-python-tests`**: delete the two combinator tests of F7 (they test `and` and
   `all`).

Steps 1, 3 and 6 are independent of the others; 2 comes before 4; 5 is independent. If only one
step is taken, take **4**: it removes the only behaviour that surprises a user.

## 8. Tests and gates

New and changed tests (one behaviour per test, `match` on every `pytest.raises`, no loop in a unit
test, literals for the expected values):

| Test (module)                                                        | Behaviour                                                             |
| -------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `test_once_false_condition_does_not_consume` (`test_manager_once.py`) | the registration is still active after a trigger whose condition is `False` |
| `test_once_false_condition_does_not_call_handler`                    | the handler is not called                                             |
| `test_once_runs_when_condition_becomes_true`                         | `AfterNCondition(2)`, 3 triggers: one call, on the third              |
| `test_once_runs_once_when_condition_stays_true`                      | 3 triggers with a true condition: one call                            |
| `test_once_raising_condition_keeps_registration`                     | the exception propagates (`match`), `active` is `True`                |
| `test_once_raising_handler_consumes_registration`                    | kept from today                                                       |
| `test_once_removed_by_earlier_handler_is_skipped`                    | kept from today (the claim fails)                                     |
| `test_subscription_constructor_options_are_keyword_only`             | `Subscription(m, "e", f, True)` raises `TypeError` (`match`)          |
| `test_subscription_repr_names_handler`                               | `Subscription(event='e', handler='print')`                            |
| `test_subscription_repr_partial_names_function_not_arguments`        | a partial of a handler with a secret argument: no secret in the text  |
| `test_check_not_awaitable_message_names_function`                    | the message of a partial has the function name and no argument        |
| `test_once_with_condition_runs_at_most_once_from_threads` (integration) | `run_threads`, a lock around the list, `once=True` and a true condition: one call |
| `test_import_does_not_create_typing_objects` (integration)           | after `import minevent`, `typing.Protocol` and `typing.NamedTuple` are not in the namespaces of `minevent.manager` and `minevent.conditions` |

Removed: the two `_Options` tests, the two combinator tests (F7), and the two tests that assert the
old consumption rule (replaced by the first two rows). Everything else is unchanged: the target
touches the order of two statements, not the contract of the other properties.

Each regression test must **fail on `main`** (`git stash push src` and run it): the rows on `once`
and on the messages do. Gates before each merge: `ruff check src tests`, `ruff format src tests`,
`ty check`, `pytest tests/unit tests/integration -q --cov=minevent --cov-branch` at 100%,
`source .venv/bin/activate && inv test.doctest`, and the benchmarks of `tests/benchmarks/` compared
with `main` for step 2 (P16). The scratch measurements above are indicative; the gate is the
benchmark.

## 9. Decisions for the maintainers

| #   | Question                                                                | Recommendation                                                                                                                                                                                                                                                                                         |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Should `once` wait for a true condition? (**reopens** a settled rule)   | **Yes.** The old rule makes two options that look independent contradict each other and costs a workaround class in the documents. The atomic claim is unchanged (one `_remove` under the lock, before the handler). The only loss is "consumed whatever the condition", which has no use: the handler never ran in that case.      |
| D2  | `Condition` as an alias instead of a `Protocol` class? (**reopens** the protocol) | **Yes.** P14 already defines a condition as `Callable[[], bool]`; the class had one method and no runtime use; the alias removes a concept and 2.2 ms of import. Alternative: keep the `Protocol` and accept 6.2 ms: nothing breaks, nothing is gained.                                                                 |
| D3  | Put the options in `repr(subscription)`?                                | **No**, event and handler name only. The options are properties; a long `repr` is not read.                                                                                                                                                                                                              |
| D4  | Name the condition when it is the callable that raised?                 | **No** (kept, listed in "Not guaranteed"). It needs a second `try` around the condition, on the hot path, to rename one note. The registration is named, which is enough to find it.                                                                                                                      |
| D5  | Split `manager.py` (868 lines, 40% docstrings) into `subscription.py` and `manager.py`? | **No.** The two classes call each other; a split adds an import cycle guarded by `TYPE_CHECKING` and a second test module to keep in step, for a file that is long because of its docstrings.                                                                                                              |
| D6  | Copy-on-write tuples to make the trigger lock-free?                     | **No.** It saves about 0.25 µs of a 0.4 µs trigger and makes a removal O(n), against P16 (_k_ removals in O(_k_)).                                                                                                                                                                                       |
| D7  | Six PRs or fewer?                                                       | **Six, stacked** (section 7). Step 4 is the only one that changes a rule; the others are mergeable in any order after their dependencies.                                                                                                                                                                |

## 10. Not covered

- **Priorities, wildcards, hierarchical events, event objects, weak references, collecting errors
  (`ExceptionGroup`), persistent or cross-process events.** Non-goals of the architecture page,
  unchanged.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). It does not change the
  runtime and needs a design of its own if users ask.
- **A handler that returns a generator** (silently dropped): rarer than the coroutine mistake, one
  more check on the hot path.
- **Free-threaded builds.** The lock covers the registry; the counters of the conditions stay
  documented as unprotected.
- **Repository tooling** (the shared `.make/` directory, the workflows, two task runners) is shared
  with other projects and outside this review.
- **A full implementation.** Only the core of steps 2 to 5 was prototyped, in a scratch copy. The
  docstrings, the documents and the final tests are part of the pull requests.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate from the prototype, the gate is the
behaviour of sections 1 and 8, not the size.

| Item                           | Today | Expected after | Why                                                                   |
| ------------------------------ | ----: | -------------: | --------------------------------------------------------------------- |
| `src/minevent/conditions.py`   |   224 |           ~190 | the `Protocol` class and its docstring become an alias                |
| `src/minevent/manager.py`      |   868 |           ~850 | `_Options` and the duplicated `once` branches out, `repr` and message in |
| `src/minevent/__init__.py`     |    48 |             48 | unchanged                                                             |
| **`src`**                      | 1,140 |        ~1,090  |                                                                       |
| `src` statements               |   235 |           ~225 | `_Options`, the two `once` branches                                   |
| `tests/unit`, `tests/integration` | 350 tests | ~355 tests | 4 out (`_Options` x2, combinators x2), about 9 in                     |
| `docs/docs`                    | 1,575 |         ~1,535 | the `FirstTrue` workaround and its text out, the table column in      |
| Runtime dependencies           |     0 |              0 |                                                                       |
| `import minevent`              | 6.2 ms |        ~4.0 ms | no `NamedTuple`, `Protocol` or `TypeVar` object at import             |
