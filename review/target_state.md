# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`c39636c`, 2026-11-23), and proposes the smallest set of changes that makes every property true.
It replaces the sixth version of this review. That version is **fully merged** (#818 to #822: the
`Subscription` owns the options, `repr` and the awaitable error name the handler, `once` waits for
its condition, `Condition` is a type alias, the combinator tests are gone), so `main` **is** the
previous target. This version starts from the result, re-reads every file, and does not repeat it.

The package is small and the design is settled: **1,127 lines** (`src`, docstrings included), **226
statements**, zero dependency, 370 tests, 100% line and branch coverage, `ruff`, `ty` and the
doctests green [verified]. There is no structural problem left. What is left is **one rule that is
not uniform, one import that costs a third of the import time, and a gap between the tests and
`CLAUDE.md`**:

- A registration removed by an earlier handler of the same trigger **still runs**, unless it is a
  `once` registration, which is skipped. The two cases are the same event (a registration is gone)
  with two different outcomes. P7 needs an exception clause to state it.
- `import minevent` loads `typing` only to read the constant `TYPE_CHECKING`: 1.7 ms of the 4.9 ms
  the import costs over a bare interpreter, and 3 of the 22 modules it loads [verified].
- The unit tests break four rules of `CLAUDE.md`: seven `contextlib.suppress` stand in for
  `pytest.raises`, four tests have a loop, `_check_event` has no test of its own, and one test has no
  assertion.
- Two documents still call `Condition` a protocol (it is a type alias since #821), and a docstring
  cites a property number of another document.

The target keeps the design (an event is a string, a handler is a callable, the manager connects
them, the `Subscription` is the registration and owns its options). Breaking changes are accepted
(the README says the API is unstable before 1.0 and nothing is released since `0.5.0`), but this
review finds **only one** that is worth making, and says so rather than inventing others.

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, one behaviour per test).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.14,
Apple laptop, throw-away prototypes kept outside the repository) or **[reading]** (from the code or
the documents). Nothing in `src`, `tests` or `docs` was changed by this review.

**Baseline on `main`** [verified]: `ruff check src tests` and `ty check` clean; 370 unit and
integration tests pass in 0.6 s with 100% line and branch coverage (`__init__` 17, `conditions` 51,
`manager` 158 statements); `import minevent` loads 22 modules that a bare interpreter does not and
takes 4.9 ms more than `python -c pass` (median of 7 runs, 15.0 ms bare, 19.9 ms with the import);
the trigger of one handler costs 0.33 µs.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, and the plain-callable _conditions_. These are the rules. Each design choice
below exists to make one of them true **by construction**. "Status" compares the row with
`docs/docs/architecture.md` today: **same** (wording kept), **changed** (the statement changes) or
**fixed** (the document was wrong). "Enforced by" names the mechanism and the test module.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                | Status  | Enforced by                                                   |
| --- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------- |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Five exported names and `__version__` (`EventManager`, `Subscription`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`. | same    | `test_init.py`                                                |
| P2  | Cheap import                 | `import minevent` is cheap and has no side effect: standard library only; it imports not `logging`, `inspect`, `asyncio`, `importlib.metadata` or **`typing`**, and it creates no `typing` object. The annotations are strings and the names of `typing` are read under `TYPE_CHECKING` only. No thread, no file, no warning, no log.                       | changed | `test_import.py` (modules and `typing` names)                 |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                       | same    | `test_manager.py`                                             |
| P4  | Validated at the door        | A wrong type raises `TypeError` in the call that receives it, with a message that names the argument and the value: the event, the handler (must be callable) and the condition (`None` or callable) of `add_event_handler` and `on`. An invalid registration leaves the manager unchanged.                                                              | same    | `add_event_handler`, `on`, `test_manager.py`                  |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`. `active` is `True` from the registration until the registration is removed, by whatever means.                                                       | changed | `Subscription`, `test_manager.py`                             |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                              | same    | the ordered `dict`, `test_manager.py`                         |
| P7  | Snapshot dispatch            | `trigger_event` visits the registrations that exist when it starts. A registration **added** by a running handler takes effect at the next trigger. A registration **removed** before its turn **does not run**, `once` or not: a removed registration never starts.                                                                                       | changed | `Subscription._call`, `test_manager.py`, `test_manager_once.py` |
| P8  | Fail-fast with context       | An exception of a handler propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and the name of the handler (the function under a `functools.partial`), once per distinct pair. No message and no `repr` of the package runs the `repr` of user data: they name the function, never its arguments. | same    | `_describe`, `_add_error_note`, `test_manager.py`             |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim just before its handler runs, after its condition, so it runs at most once whatever the number of threads. A false or raising condition does not consume it; a handler that raises does.                                                                                                              | same    | `Subscription._call`, `test_manager_once.py`, `test_manager_threads.py` |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop. An object with `async def __call__` is a coroutine handler like a coroutine function.                                    | same    | `_check_not_awaitable`, `test_manager_async.py`               |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                                                                                                               | same    | `EventManager._lock`, `test_manager_threads.py`               |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependencies. A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`).                                                                                                                                                      | same    | `__reduce__`, `test_manager.py`                               |
| P13 | Payload is data              | `trigger_event(event, /, **payload)` calls every handler as `handler(**payload)`. Any key is allowed (`event`, `self`). Arguments that do not come from the payload are bound with `functools.partial`. With `filter_payload=True` only the keys the signature accepts are passed.                                                                          | same    | `trigger_event`, `test_manager.py`                            |
| P14 | Options are per registration | `once`, `condition` and `filter_payload` are keyword-only arguments of `add_event_handler` and `on` (and of the `Subscription` constructor), with the same names, defaults and meaning. A condition is a `Condition = Callable[[], bool]`, called once per trigger, before the handler. The built-in conditions keep per-instance state and have `reset()`.   | same    | signatures, `test_manager.py`, `test_conditions.py`           |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                                                                                       | same    | `ty check` in CI                                              |
| P16 | Fast and linear              | A trigger of one handler costs about 0.35 µs, each extra handler about 0.1 µs, a registration plus its removal about 0.65 µs (Python 3.14, laptop). Registering _k_ handlers and removing them in any order costs O(_k_) in total. Benchmarks guard it.                                                                                                   | changed | `tests/benchmarks/`                                           |
| P17 | A manager is a service       | `bool(manager)` is always `True`, empty or not, so `manager or default` means "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                                                                       | same    | `__bool__`, `test_manager.py`                                 |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to bind arguments (`functools.partial`), one way to run a handler once (`once=True`), one way to extend (write a callable). No handler base class.                                                                                                                    | same    | the signatures                                                |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function, `repr(manager)` counts the registrations per event. The library logs nothing: `get_subscriptions(event)` is the way to look.                                                                                                                                                                | same    | `__repr__`, `test_manager.py`                                 |

Not guaranteed, and documented as such (listed so the target is complete; the first item of the
previous version is **gone**, see 4.1):

- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A handler that returns a generator** does nothing: only awaitables are detected (P10).
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  dict, `Subscription`, manager): `del manager` does not free it until the garbage collector runs
  [verified: the weak reference is still alive after `del`, dead after `gc.collect()`]. `reset()`
  releases the handlers at a known point.
- **State of a condition under threads.** The counter of `PeriodicCondition` and `AfterNCondition` is
  not protected: a stateful condition should be triggered from one thread. A `once` registration
  whose condition is evaluated by two threads at once runs once, but both evaluations advance the
  counter.
- **A removal in another thread.** P7 is exact in the thread that triggers: a handler that removes a
  later registration of the same trigger prevents it. Another thread that calls `remove()` while a
  trigger is between the check and the call of that handler cannot prevent that one start. After a
  trigger returns, a removed registration has not run.
- **A keyword bound by `functools.partial` and given again by the payload**: the payload wins.
- **A condition that raises** gets the note of its registration (`raised by <handler> ...`): the
  note names the registration, not the callable that raised.

## 2. Constraints on the target

1. **Simple and easy to maintain.** A change deletes code or documents a rule once. It adds code
   only if the code removes a more complex rule.
2. **Breaking changes are fine** and compatibility is not a design input: no alias, no deprecation
   period. The changelog lists them.
3. **No slower than today.** P16 is measured before and after (section 6).
4. **No dependency**, standard library only, heavy imports lazy (`CLAUDE.md`).
5. **Settled decisions stay settled** unless a defect is shown: sequential async, fail-fast,
   `get_subscriptions`, a lock in the manager and none in the conditions, the note without `repr`, a
   dict as an ordered set, the two dispatch loops not shared, a condition without the payload, a
   truthy and non-copyable manager, one module `manager.py`, the options as properties and not in
   the `repr`. Section 9 lists the one that this review **reopens** (the snapshot, P7) and why.

## 3. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1  | **A removed registration runs, except a `once` one.** Handler `h1` calls `subscription2.remove()` and then `h2` (the registration that was removed) runs: the output is `['h1', 'h2']`. If `h2` was registered with `once=True`, `_call` fails the claim and skips it [verified]. The cause is that "removed" is only visible in the registry, and only the `once` claim reads the registry. P7 states the exception ("except that a `once` registration removed by an earlier handler of the same trigger does not run"), the guide, the FAQ and `trigger_event` repeat it, and "a handler removed while a trigger is running still runs" is the first item of the "Not guaranteed" list. |
| F2  | **The import loads `typing` for a constant.** `from typing import TYPE_CHECKING` is the only runtime use of `typing`. Without it the import loads 19 modules instead of 22 and costs 3.2 ms over a bare interpreter instead of 4.9 ms (-35%, median of 21 runs) [verified, prototype]. `ty check` passes with `TYPE_CHECKING = False`, and `ruff` reports only an import-block blank line.                                                                                                                                                                                                      |
| F3  | **The unit tests do not follow `CLAUDE.md`** [verified by an AST audit and `grep`]: (a) seven `contextlib.suppress` stand in for `pytest.raises` (`test_manager.py` 196, 272, 286, 300; `test_manager_once.py` 157; `test_manager_async.py` 94, 234), so a test passes when nothing raises; (b) four tests of `test_manager_once.py` (lines 247, 255, 263, 271) loop in the body; (c) `_check_event` is a function with no test of its own (it is only reached through the public methods); (d) `test_event_manager_clear_event_missing` has no assertion.                                                              |
| F4  | **The documents have three stale statements** [reading]: `quickstart.md:161` and `architecture.md:288` call `Condition` "the `Condition` protocol" (it is `Callable[[], bool]` since #821); the `add_event_handler` docstring (`manager.py:520`) cites "P9 of the architecture page", a number that changes when the table is renumbered and that mkdocs does not link; `architecture.md` P16 gives 0.4 µs and 0.1 µs where the measurement is 0.33 µs and 0.1 µs.                                                                                                                                      |
| F5  | **`Subscription.active` and `Subscription._call` cannot see a removal without the manager.** `active` calls the private `EventManager._is_registered` (lock, `dict` lookup); `_remove` is the only place that knows the registration is gone. This is the cause of F1, and it is why a cheap check in `_call` does not exist today [reading].                                                                                                                                                                                  |

What is already right and must not regress: callables as handlers; the options as keyword-only
arguments owned by the `Subscription`; the atomic claim under the lock; the note that names the
function and is deduplicated; `repr` that names the function; `once` that waits for its condition;
`Condition` as an alias; the lazy `inspect` and `__version__`; `bool(manager)`; the non-copyable
manager; 100% coverage.

Measured and kept (P16, Python 3.14, best of 5 or 7, 200,000 to 500,000 triggers):

| Case                       | Time per trigger |
| -------------------------- | ---------------: |
| no handler                 |         0.194 µs |
| 1 handler                  |         0.331 µs |
| 10 handlers                |         1.200 µs |
| add + remove one handler   |         0.620 µs |

## 4. Target design

### 4.1 A removed registration never starts (P5, P7)

The `Subscription` records that it was removed. The registry stays the source of truth for the
manager (it decides what a trigger visits); the flag is the source of truth for the question "was
this registration removed?", which `_call` and `active` ask. One writer sets it, in the three places
that take a registration out of the registry:

```python
class Subscription:
    def __init__(self, manager, event, handler, *, once=False, condition=None, filter_payload=False):
        ...
        self._active = True  # set to False by the manager when the registration leaves the registry

    @property
    def active(self) -> bool:
        return self._active

    def _call(self, payload: dict[str, object]) -> object:
        if not self._active:
            return None  # removed before its turn: by remove(), a once claim, clear_event or reset
        if self._condition is not None and not self._condition():
            return None
        if self._once and not self.remove():
            return None  # lost the claim to another thread
        ...


class EventManager:
    def _remove(self, subscription):
        with self._lock:
            subs = self._subscriptions.get(subscription.event)
            if subs is None or subscription not in subs:
                return False
            del subs[subscription]
            subscription._active = False
            ...

    def clear_event(self, event):
        with self._lock:
            for subscription in self._subscriptions.pop(event, {}):
                subscription._active = False

    def reset(self):
        with self._lock:
            for subs in self._subscriptions.values():
                for subscription in subs:
                    subscription._active = False
            self._subscriptions.clear()
```

What changes for a user:

| Situation                                                        | Today                      | Target                                |
| ---------------------------------------------------------------- | -------------------------- | ------------------------------------- |
| `h1` calls `subscription2.remove()`, `h2` is that registration   | `h2` **runs**              | `h2` is skipped                       |
| the same, `h2` registered with `once=True`                       | skipped (the claim fails)  | skipped (unchanged)                   |
| `h1` calls `manager.clear_event(e)` or `manager.reset()`         | the rest of the snapshot **runs** | the rest is skipped            |
| `h1` registers `h3` for the same event                           | `h3` runs at the next trigger | same                               |
| a handler removes itself                                         | runs once more at most, then gone | same                           |

Consequences, all deletions or simplifications:

- P7 loses its exception clause and becomes one sentence about removal. The "removed while a trigger
  is running still runs" limit (architecture, guide pitfalls, FAQ, `trigger_event` docstring)
  disappears from four documents.
- `EventManager._is_registered` (a private method with a docstring and its own tests) is deleted:
  `active` reads the flag.
- The `once` claim is unchanged (one `_remove` under the lock, after the condition, before the
  handler). The `_active` check in front of it is the same fact read earlier and without the lock, so
  it is an optimisation of a case the claim already handles, not a second mechanism.
- Cost: one attribute read per handler (`0.338 µs` against `0.335 µs` for one handler, `1.246 µs`
  against `1.200 µs` for ten, noise on this laptop) [verified, prototype]. `clear_event` and `reset`
  become O(registrations) instead of O(1), which is the cost of making their subscriptions inactive
  and is paid once per call, not per trigger.
- `Subscription(manager, event, handler)` that is built by hand and never registered reports
  `active is True` (the prototype with an initial `False` broke 7 `_call` tests that call the
  method on a bare subscription, so the flag starts `True`). The constructor is documented internal;
  the two tests that asserted "never registered is inactive" are deleted with the claim.

The exactness of P7 is bounded by threads (section 1, "A removal in another thread"): the flag is
read without the lock, so a thread can pass the check just before another thread removes the
registration. Closing that window needs the lock around every handler call, which breaks P11 (a
handler runs outside the lock). The documents state the bound once.

### 4.2 `import minevent` loads no `typing` module (P2)

```python
# manager.py
TYPE_CHECKING = False

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType
    from typing import NoReturn, Self, TypeVar

    from minevent.conditions import Condition

    _F = TypeVar("_F", bound=Callable[..., object])
```

`conditions.py` and `__init__.py` already import no `typing`. `TYPE_CHECKING = False` is the idiom
that type checkers recognise as the constant; `ty check` passes on it [verified]. The imported
modules go from 22 to 19, and the import from 4.9 ms to 3.2 ms over a bare interpreter. The
integration test that lists the modules the import must not load gets `typing` in `LAZY_MODULES`
(it replaces the five tests of the `typing` names, which become redundant: if `typing` is not
imported, none of its objects is created).

### 4.3 The tests follow `CLAUDE.md` (F3)

| Defect                              | Target                                                                                                                                                                                                                      |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `contextlib.suppress(E)` then assert | `with pytest.raises(E, match=r"...")` then the assertion on the state, one test. The seven tests keep their name and assertion; the `match` is the message of the raised error.                                          |
| loops in four `once` tests          | `@pytest.mark.parametrize("n_triggers", ...)` for the count, or a helper that triggers `n` times and returns the manager (a function, so the test body has no loop).                                                      |
| `_check_event` has no test          | `test_check_event_accepts_str`, `test_check_event_rejects_non_str` (parametrized over `1`, `None`, `b"e"`, with `match=r"event must be a str, but got"`), and the message names the type.                                 |
| `clear_event_missing`               | `assert manager.events == []` after the call: the behaviour is "nothing happens and no event appears".                                                                                                                     |

No source change. The `contextlib` imports of the three modules go away.

### 4.4 One home per fact in the documents (F4)

| Fact                                   | Home                                           | Elsewhere                    |
| -------------------------------------- | ---------------------------------------------- | ---------------------------- |
| The rules (P1 to P19), the limits      | `architecture.md` (the table, "Enforced by")   | linked by name, never by number in `src` |
| One recipe per task                    | `guide.md`                                     | no restatement of a rule     |
| The tutorial, runnable examples        | `quickstart.md`                                | no restatement of a rule     |
| Signature, arguments, `Raises`         | the docstrings                                 | rendered by `mkdocstrings`   |
| What the package is, how to install    | `README.md`, `index.md`, `get_started.md`      | unchanged                    |

Concretely: "the `Condition` protocol" becomes "a `Condition`, that is a `Callable[[], bool]`"
(quickstart, architecture); the `once` sentence of the `add_event_handler` docstring says "so it
runs at most once, even when several threads trigger the event" and cites no property number; P16
gets the measured timings; the removal rule (4.1) is written in P7, the guide's pitfalls, the FAQ
and the `trigger_event` docstring, and the "removed while running" bullets are deleted.

## 5. Public API after the change

Unchanged. The surface does not grow and does not shrink:

```python
from minevent import (
    EventManager,
    Subscription,
    Condition,  # Callable[[], bool]
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

### Migration

- A program that removes a registration from a running handler and **relied on that registration
  still running in the same trigger** (no known use) must move the work to the remover.
- `Subscription(manager, event, handler)` built by hand and never registered is `active`. Use
  `add_event_handler`.
- Nothing else breaks. `import minevent` loads fewer modules.

## 6. Evidence

Prototypes in scratch copies of `src` and `tests` (outside the repository), with the existing suite
run against them.

**Behaviour** [verified, prototype of 4.1]:

| Probe                                                               | `main`                   | Prototype                |
| ------------------------------------------------------------------- | ------------------------ | ------------------------ |
| `h1` removes the registration of `h2`, then triggers                | `['h1', 'h2']`           | `['h1']`                 |
| same, `h2` registered with `once=True`                              | `['h1']`                 | `['h1']`                 |
| `once=True` + `AfterNCondition(2)`, 3 triggers                      | 1 call                   | 1 call                   |
| `subscription.active` after `reset()`                               | `False`                  | `False`                  |
| thread tests of `once` (at most once under contention)              | pass                     | pass                     |

**Suite against the prototype**: 355 tests pass and **3 fail, all 3 changed behaviours**
(`test_event_manager_trigger_event_handler_removed_during_dispatch_still_runs` and the two tests
that call a never-registered subscription inactive). The suite file `tests/unit/test_benchmark_trend.py`
needs the repository root on the path and was run from the repository.

**Import** [verified, prototype of 4.2]:

| Measure                                      | `main` | Prototype |
| -------------------------------------------- | -----: | --------: |
| Modules loaded by the import                 |     22 |        19 |
| Time of `python -c "import minevent"` (ms)   |   20.1 |      18.4 |
| Bare interpreter (ms)                        |   15.2 |      15.2 |
| Import over the bare interpreter (ms)        |    4.9 |       3.2 |

**Speed** [verified, prototype of 4.1]:

| Measure                          | `main` | Prototype |
| -------------------------------- | -----: | --------: |
| Trigger, 1 handler (µs)          |  0.335 |     0.338 |
| Trigger, 10 handlers (µs)        |  1.200 |     1.246 |

Within noise (the `once` claim is untouched; each handler pays one attribute read).

## 7. Changes to reach the target state

One branch and one pull request per step, stacked where a step depends on another (`CLAUDE.md`),
each mergeable alone and green.

1. **`test/follow-the-test-rules`** (no source change): replace the seven `contextlib.suppress` by
   `pytest.raises` with `match`, remove the four loops, add the tests of `_check_event`, assert in
   `clear_event_missing`. First, because step 3 touches the same files and the tests should be right
   before they are changed.
2. **`refactor/import-without-typing`**: `TYPE_CHECKING = False`; `typing` in `LAZY_MODULES`; the
   five `typing`-name tests removed; P2 and the guide's performance paragraph updated, with the
   measurement in the description. Independent of the others.
3. **`feat/removed-registration-never-runs`** (**breaking**, small): the `_active` flag, the three
   writers, `active` reads it, `_is_registered` and its tests deleted, P5 and P7 rewritten, the four
   documents lose the "removed while running" limit, changelog entry with the migration.
4. **`docs/fix-stale-statements`**: "the `Condition` protocol" (two places), the property number in
   the docstring, the timings of P16. No code. Can go first if wanted.

Steps 1, 2 and 4 are independent. Step 3 comes after step 1 (the same test files). If only one step
is taken, take **1**: the other findings are cosmetic or a trade-off, and the rules of `CLAUDE.md`
are the ones a reviewer can check mechanically.

## 8. Tests and gates

New and changed tests (one behaviour per test, `match` on every `pytest.raises`, no loop in a unit
test, literals for the expected values):

| Test (module)                                                                   | Behaviour                                                                  |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `test_check_event_accepts_str` (`test_manager.py`)                               | returns `None` for `"e"` and for `""`                                      |
| `test_check_event_rejects_non_str` (parametrized)                                | `TypeError`, `match=r"event must be a str, but got"`                       |
| `test_event_manager_clear_event_missing`                                         | `manager.events == []` after clearing an unknown event                     |
| `test_once_does_not_run_before_condition_is_true` and three more (`test_manager_once.py`) | the same behaviours, parametrized or with a helper, no loop in the body |
| `test_trigger_event_removed_registration_does_not_run`                           | `h1` removes `h2`'s subscription: `h2.call_count == 0`                     |
| `test_trigger_event_removed_by_clear_event_does_not_run`                         | `h1` calls `clear_event`: the next handler does not run                    |
| `test_trigger_event_removed_by_reset_does_not_run`                               | `h1` calls `reset`: the next handler does not run                          |
| `test_trigger_event_added_during_dispatch_runs_next_trigger`                     | kept from today                                                            |
| `test_subscription_active_false_after_remove` / `..._clear_event` / `..._reset`  | the flag follows each of the three ways                                    |
| `test_subscription_call_removed_returns_none`                                    | `_call` on a removed registration does not call the handler                |
| `test_import_minevent_does_not_import_module[typing]` (integration)              | `typing` is not in `sys.modules` after the import                          |
| `test_remove_from_threads_while_triggering` (integration, `run_threads`)         | the handler runs at most once per registration; after the join, none runs  |

Removed: the two "never registered is inactive" tests, the tests of `_is_registered`, the five
`typing`-name tests. A test that the flag and the registry agree (`active` is `True` if and only if
`subscription in manager.get_subscriptions(event)`) is added as a parametrized test over the three
ways of removing and over the three ways of not removing. Each regression test must **fail on
`main`** (`git stash push src` and run it): the rows on removal do.

Gates before each merge: `ruff check src tests`, `ruff format src tests`, `ty check`,
`pytest tests/unit tests/integration -q --cov=minevent --cov-branch` at 100%,
`source .venv/bin/activate && inv test.doctest`, and the benchmarks of `tests/benchmarks/` compared
with `main` for steps 2 and 3 (P16). The scratch measurements above are indicative; the gate is the
benchmark.

## 9. Decisions for the maintainers

| #   | Question                                                                | Recommendation                                                                                                                                                                                                                                                                                                                       |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Skip a registration removed before its turn? (**reopens** P7)           | **Yes.** One rule for `once` and plain registrations, one limit less in four documents, `_is_registered` deleted, no measurable cost. The loss is the "snapshot is frozen" reading (Node's `EventEmitter`); the DOM and `blinker` skip removed listeners. Added registrations still wait for the next trigger, so the snapshot keeps its protection against endless loops. Alternative: keep P7 and accept the exception clause; nothing breaks, nothing is gained. |
| D2  | `TYPE_CHECKING = False` instead of `from typing import TYPE_CHECKING`?  | **Yes.** -35% of the import for one line; recognised by `ty`. Alternative: keep the import (1.7 ms).                                                                                                                                                                                                                                  |
| D3  | Break the manager/subscription cycle with a weak reference?             | **No.** It adds an import (`weakref`), a dead-manager branch in `remove` and `active`, and a rule to document, to free handlers a few milliseconds earlier than the collector. `reset()` is the documented way to release at a known point.                                                                                          |
| D4  | Name the condition when it is the callable that raised?                 | **No** (kept, listed in "Not guaranteed"). It needs a second `try` around the condition on the hot path to rename one note. The registration is named, which is enough to find it.                                                                                                                                                    |
| D5  | Lock around every handler call to make removal exact across threads?    | **No.** It contradicts P11 (handlers run outside the lock, so that a handler can use the manager) and costs a lock acquisition per handler. The documents state the bound (section 1).                                                                                                                                                 |
| D6  | Make `Subscription` impossible to construct by hand?                    | **No.** Python cannot forbid it; the constructor is documented internal, and the tests of `_call` build subscriptions without a manager registry, which is what keeps them fast and simple.                                                                                                                                            |
| D7  | Four PRs or fewer?                                                      | **Four** (section 7). Step 3 is the only one that changes a rule; the others change nothing a user can observe except the import time.                                                                                                                                                                                                |

## 10. Not covered

- **Priorities, wildcards, hierarchical events, event objects, weak references, collecting errors
  (`ExceptionGroup`), persistent or cross-process events.** Non-goals of the architecture page,
  unchanged.
- **Return values of handlers.** `trigger_event` returns `None`; a handler that must produce a value
  writes it where the caller reads it. A result list would force an order and an error policy.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). It does not change the
  runtime and needs a design of its own if users ask.
- **A handler that returns a generator** (silently dropped): rarer than the coroutine mistake, one
  more check on the hot path.
- **Concurrent async dispatch** (`asyncio.gather` over the coroutine handlers). It would give up the
  registration order (P6) and the fail-fast rule; a handler that needs concurrency starts its own
  tasks.
- **Free-threaded builds.** The lock covers the registry; the counters of the conditions stay
  documented as unprotected.
- **Validation of the boolean options.** `once="yes"` and `filter_payload=1` are accepted and read
  as truthy [verified]. A validator that is one `isinstance` is excluded by `CLAUDE.md`.
- **Repository tooling** (the shared `.make/` directory, the workflows, `dev/benchmark_trend.py`
  and its tests) is shared with other projects and outside this review.
- **A full implementation.** Only the core of steps 2 and 3 was prototyped, in scratch copies. The
  docstrings, the documents and the final tests are part of the pull requests.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate from the prototypes, the gate is the
behaviour of sections 1 and 8, not the size.

| Item                              |  Today | Expected after | Why                                                                                  |
| --------------------------------- | -----: | -------------: | ------------------------------------------------------------------------------------ |
| `src/minevent/conditions.py`      |    210 |            210 | unchanged                                                                            |
| `src/minevent/manager.py`         |    869 |           ~865 | the flag and three writers in, `_is_registered` and its docstring out                |
| `src/minevent/__init__.py`        |     48 |             48 | unchanged                                                                            |
| **`src`**                         |  1,127 |         ~1,123 |                                                                                      |
| `src` statements                  |    226 |           ~232 | one flag, three writers, one check, one loop in `reset`, minus `_is_registered`      |
| `tests/unit`, `tests/integration` | 370 tests |   ~375 tests | out: 2 (never registered), `_is_registered`, 5 (`typing` names); in: about 14        |
| `docs/docs`                       |  1,562 |         ~1,545 | the "removed while running" limit out of four documents                              |
| Runtime dependencies              |      0 |              0 |                                                                                      |
| `import minevent` over a bare interpreter | 4.9 ms | ~3.2 ms | no `typing` module                                                                   |
