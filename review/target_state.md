# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`335e29b`, 2026-11-01), and proposes the smallest set of changes that makes every property true.
It replaces the first version of this review: its eleven steps are merged (one registration record,
conditions as callables, no equality protocol, no `coola`, merged guide, benchmark suite), so this
version starts from the result and only looks at what is left. The package is now small (1,282
lines, 276 statements, 0 dependencies), so the remaining work is short: **two defects, one
inconsistency, three simplifications and the documents that drifted**. Breaking changes are accepted
(the README says the API is unstable before 1.0), and every name removed below is in `Unreleased`,
so removing it is free.

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, no cross-module private helpers).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.13.3,
scripts kept outside the repository) or **[reading]** (from the code or the documents). Nothing in
`src`, `tests` or `docs` was changed by this review.

## Constraints

1. **Simple and easy to maintain.** Fewer concepts, fewer modules, one way to do each thing. A
   change that adds code must remove a defect or a duplicate.
2. **Breaking changes are accepted.** Migration notes go in `CHANGELOG.md`, with the PR number.
3. **No slower than today.** Benchmark gate in section 8: a row more than 10% slower needs a reason.
4. **Documented guarantees are true.** Every property of section 1 has a test, and the documents say
   nothing the code does not do.
5. **No runtime dependency, heavy imports lazy.** Standard library only; `inspect` and
   `importlib.metadata` are not imported until used.
6. **Python `>=3.11`.** `BaseException.add_note` and `typing.Self` are used.

---

## 1. Properties of the sub-package

| #   | Property                 | Statement                                                                                                                                                                                                                                                                               | Enforced by                                            |
| --- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| P1  | Small surface            | Three concepts: _event_ (a `str`), _event handler_, _event manager_. Plus the `Subscription` returned by a registration and plain-callable _conditions_. Seven exported names and `__version__`.                                                                                        | `__all__` reviewed in each PR                          |
| P2  | Events are strings       | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                      | unit tests (exist)                                     |
| P3  | Validated at the door    | A wrong type raises `TypeError` **in the call that receives it**, not later in the dispatch: the event, the handler of `add_event_handler`, the callable and the arguments of `EventHandler`, the condition.                                                                            | unit tests (handler check is new, **F2**)              |
| P4  | Registration identity    | `add_event_handler` returns a new `Subscription` every time; the same handler can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`.                                                                                    | unit tests (exist)                                     |
| P5  | Registration order       | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                             | unit tests (exist)                                     |
| P6  | Snapshot dispatch        | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                                                                | unit tests (exist)                                     |
| P7  | Fail-fast with context   | An exception of a handler propagates **unchanged** (same object, same type) to the caller; the remaining handlers are skipped. It carries a note with the event and the handler callable. Building the note never runs the `repr` of user data (arguments, keyword arguments, payload). | unit tests (exist; the `repr` clause is new, **F1**)   |
| P8  | `once` is at-most-once   | A `once` registration is removed **before** its handler is called, by an atomic claim: it runs at most once whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                                                                    | barrier test (exists)                                  |
| P9  | Synchronous by default   | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError`. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop.                                                                                     | unit tests (exist)                                     |
| P10 | Thread-safe registry     | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run **outside** the lock, so a handler can use the manager.                                                                                                                          | threads integration tests (exist)                      |
| P11 | No hidden state          | No global manager, no discovery, no registration side effect of a read. Zero runtime dependencies, and `import minevent` does not import `inspect` or `importlib.metadata`.                                                                                                             | `package_checks.py` (the import clause is new, **F4**) |
| P12 | Payload is data          | `trigger_event(event, /, **payload)` passes the payload to every handler as keyword arguments, after `handler_kwargs`. Any key is allowed (`event`, `self`). With `filter_payload=True` only the keys the signature accepts are passed.                                                 | unit tests (exist)                                     |
| P13 | Conditions are callables | A condition is a `Callable[[], bool]`, called once per trigger and per handler, before the handler. The built-in conditions keep per-instance state; sharing an instance shares the state. There is **one** way to run a handler once (`once=True`).                                    | unit tests (exist; the last clause is new, **F6**)     |
| P14 | Typed                    | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                      | `ty` in CI (exists)                                    |
| P15 | Fast                     | A trigger of one handler costs about 0.7 µs, a registration plus its removal about 0.65 µs, an import about 10 ms. Not slower than today.                                                                                                                                               | benchmark gate (section 8)                             |

### Not guaranteed, and documented as such

- **Order across threads.** Two threads that trigger the same event run the handlers concurrently,
  in no defined interleaving. A handler that shares state must protect it.
- **State of conditions under threads.** `PeriodicCondition` and `AfterNCondition` update a counter
  without a lock (D8 of the first review, unchanged).
- **A handler removed while a trigger is running** still runs in that trigger (P6). After `remove()`
  returns, the next trigger does not run it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **Copy and pickle.** An `EventManager` holds a lock: `copy.deepcopy` and `pickle` raise `TypeError`
  **[verified]**. Create a new manager instead.

---

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Status         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| F1  | **P7 is false: the error note can replace the handler's exception.** `_add_error_note` puts `repr(event_handler)` in the note, and `EventHandler.__repr__` prints `handler_args`, `handler_kwargs` and the condition. With `EventHandler(h, [BadRepr()])`, where `h` raises `ValueError("handler failed")` and `BadRepr.__repr__` raises, the caller receives `RuntimeError: repr boom`, not the `ValueError`. With a 100,000-element list as argument the note is **689,053 characters** long (it lands in every traceback and log).                                          | **[verified]** |
| F2  | **P3 is false for the handler.** The event is checked at registration; the handler is not. `manager.add_event_handler("e", print)` succeeds, and the error comes at the first trigger, possibly hours into a run: `AttributeError: 'builtin_function_or_method' object has no attribute 'handle'`.                                                                                                                                                                                                                                                                             | **[verified]** |
| F3  | **The documents drifted.** The docstring of `trigger_event` still says "The last triggered event name is updated regardless of whether any handlers are registered" (the property was removed). `architecture.md` shows the registry as lists of handlers and states "`O(n)` handler lookup (n = total handlers)" (it stores `Subscription`s and has no lookup). `README.md` keeps a `coola` column in the version table of a package that has no dependency. Its "Properties" list is a shorter copy of section 1 with different wording.                                     | **[verified]** |
| F4  | **`inspect` is imported by every user and called on every handler call.** `import minevent` takes 13.2 ms, and `inspect` shows 6.8 ms of it (cumulative); moving it out saves 3.6 ms measured. It is used by `_accepted_keywords` (only for `filter_payload=True`) and, on the hot path, by `inspect.isawaitable(result)` after **every** handler call (about 200 ns more than `result is not None and isinstance(result, collections.abc.Awaitable)`, which is 33 ns for the usual `None`, `timeit`). `CLAUDE.md` asks for lazy heavy imports, as `__version__` already does. | **[verified]** |
| F5  | **Two modules share private state.** `manager.py` writes `subscription._active` (in `_remove`, `clear_event` and `reset`) and reads `_once` and `_event_handler`; `subscription.py` calls `manager._remove` and imports the manager under `TYPE_CHECKING` (a cycle). `CLAUDE.md` forbids private helpers imported across modules. The record and its registry are one concept in two files (146 + 466 lines), tested in two files.                                                                                                                                             | **[reading]**  |
| F6  | **`OnceCondition` duplicates `once=True` and is weaker.** The quickstart says so itself ("`add_event_handler(..., once=True)` and `OnceCondition` are two ways to run a handler once", `quickstart.md:182`). `once=True` is claimed atomically under the lock; `OnceCondition` is an unlocked flag that two threads can both read as unset, and it leaves a dead registration in `len(manager)`. It is in `Unreleased`, mentioned in 6 documents and in the benchmarks.                                                                                                        | **[reading]**  |
| F7  | **`_snapshot` duplicates `get_subscriptions`.** Both check the event and copy the list under the lock; `_snapshot` adds one `logger.debug`. It exists only to share that line between `trigger_event` and `atrigger_event`, and has its own tests.                                                                                                                                                                                                                                                                                                                             | **[reading]**  |
| F8  | **Two benchmark mechanisms.** `dev/benchmark.py` (82 lines, `timeit`) measures seven rows, every one of which is also in `tests/benchmarks/` (419 lines, `pytest-benchmark`, run by `inv test.benchmark` and the nightly workflow). Nothing in `CONTRIBUTING.md`, the README or the guide refers to the script; the gate of the first review points at it.                                                                                                                                                                                                                     | **[reading]**  |

### Measured and kept

- **Debug logging.** A disabled `logger.debug` costs 83 ns, so the line in each trigger is about 12%
  of a one-handler trigger (706 ns). It is what tells a user "my handler does not run" that the
  event was fired at all (`guide.md`, Debug). Kept (D6).
- **Exceptions of conditions** (`once` consumed, note added): works as P7 and P8 say **[verified]**.
- **Subclasses of `str` as events**, and unhashable events in `in`: a `str` subclass is accepted
  and found; `[] in manager` raises the `TypeError` of `dict` **[verified]**. Not changed.

### What already works and must not regress

- Snapshot dispatch with the handlers outside the lock (P6, P10), `RLock` so a handler can use the
  manager, and `once` claimed atomically (0 failures in 200 rounds of 8 threads in the first review).
- `event` and `self` as payload keys (`event` is positional-only), the awaitable check in `handle`
  (a coroutine is closed, so no `RuntimeWarning`), `filter_payload`, `handler_kwargs` copied,
  `str` and `bytes` `handler_args` rejected.
- `Subscription` identity by default: `list.remove(sub)` removes that record.
- Fail-fast and the non-goals (event objects, priorities, weak references, collecting errors).
- 295 tests, 100% line and branch coverage, `ruff` and `ty` clean, `filterwarnings = error`.

---

## 3. Architecture

```text
EventManager ──registry──▶ {event: [Subscription, ...]}      insertion order = run order
     │                          event, event_handler, once, active
     │ trigger_event(event, /, **payload)
     ▼
for sub in get_subscriptions(event):        # a tuple copy, under the lock
    if sub.once and not _remove(sub):       # atomic claim (P8)
        continue
    sub.event_handler.handle(**payload)     # outside the lock
         │
         ▼
EventHandler.handle ──▶ condition() ──▶ filter payload ──▶ handler(*args, **kwargs, **payload)
```

The design of the first review is kept; it is already the smallest that has all the properties.
Three modules after the change instead of four:

| Module          | Contains                                                     |
| --------------- | ------------------------------------------------------------ |
| `conditions.py` | `Condition` protocol, `PeriodicCondition`, `AfterNCondition` |
| `handlers.py`   | `BaseEventHandler`, `EventHandler`                           |
| `manager.py`    | `EventManager`, `Subscription`                               |

### 3.1 Registration and the record (F2, F5, F7)

`Subscription` moves into `manager.py`, next to the only code that creates it and changes its state.
Reading and writing `_active` and `_once` inside one module is ordinary; the cycle and the
`TYPE_CHECKING` import disappear. `from minevent import Subscription` is unchanged; the module
`minevent.subscription` is removed (it was never released).

`add_event_handler` validates its two arguments, like `EventHandler` validates its own:

```python
def add_event_handler(self, event, event_handler, *, once=False) -> Subscription:
    _check_event(event)
    if not isinstance(event_handler, BaseEventHandler):
        msg = (
            "event_handler must be a BaseEventHandler, but got "
            f"{type(event_handler).__qualname__}: wrap a function with EventHandler(func)"
        )
        raise TypeError(msg)
    ...
```

`trigger_event` and `atrigger_event` call `self.get_subscriptions(event)`; `_snapshot` is deleted.
Each loop keeps its own `logger.debug("Firing %s event", event)` (one line, no helper).

### 3.2 The error note (F1)

```python
def _describe(event_handler: BaseEventHandler) -> str:
    """Name a handler without calling the repr of its data."""
    target = event_handler.handler if isinstance(event_handler, EventHandler) else event_handler
    return getattr(target, "__qualname__", type(target).__qualname__)


def _add_error_note(exc, event, event_handler) -> None:
    exc.add_note(f"raised by {_describe(event_handler)} while handling the event {event!r}")
```

The note names the event (a `str`, so safe) and the **callable**: `hello_handler`,
`Trainer.on_epoch_end`, `partial` (a `functools.partial`) or the class of a callable instance, or the
class of a custom `BaseEventHandler`. It is a few dozen characters whatever the arguments. The full
`repr` stays available in the debug log and in the debugger. `EventHandler.__repr__` is unchanged.

### 3.3 Awaitable check without `inspect` (F4)

```python
from collections.abc import Awaitable, Coroutine

# EventHandler.handle
result = self._call(payload)
if result is not None and isinstance(result, Awaitable):
    if isinstance(result, Coroutine):
        result.close()
    raise TypeError(f"{self._handler!r} returned an awaitable; use ahandle or atrigger_event")

# EventHandler.ahandle
if result is not None and isinstance(result, Awaitable):
    await result
```

`inspect` is imported inside `_accepted_keywords`, the only other user, so a user who never sets
`filter_payload=True` never pays for it. The one behaviour difference: `inspect.isawaitable` also
accepts a legacy generator-based coroutine (`types.coroutine`); `Awaitable` does not. Such an object
is not produced by `async def`; it is documented and not handled.

### 3.4 Conditions (F6)

`OnceCondition` is deleted. `once=True` is the one way to run a handler once. The rest of
`conditions.py` is unchanged. For "run on the first call where my own predicate is true", write it:

```python
done = False


def first_improvement() -> bool:
    global done
    if done or not has_improved():
        return False
    done = True
    return True
```

(or a class with `__call__`, as the guide shows for custom conditions).

---

## 4. Public API after the change

```python
# minevent/__init__.py
__all__ = [
    "AfterNCondition",
    "BaseEventHandler",
    "Condition",
    "EventHandler",
    "EventManager",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]
```

Signatures are unchanged, except that `add_event_handler` raises `TypeError` for a handler that is
not a `BaseEventHandler`. The package goes from 8 exported names plus `__version__` to 7 plus
`__version__`; `EventManager` keeps its 9 public members.

### Migration

| Code                                              | After                                                                              |
| ------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `OnceCondition()`                                 | `add_event_handler(..., once=True)`, or a function with a flag                     |
| `from minevent.subscription import Subscription`  | `from minevent import Subscription`                                                |
| `manager.add_event_handler("e", func)`            | `manager.add_event_handler("e", EventHandler(func))` (was a late `AttributeError`) |
| `"raised by EventHandler(handler=..., ...)"` note | `"raised by <callable name> while handling the event 'e'"`                         |

---

## 5. Dependents

| Place                                  | Change                                                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/docs/architecture.md`            | Replace its "Properties" list by the table of section 1 (same ids). Fix the internal structure (`Subscription`s), delete "O(n) handler lookup". Update the note example. |
| `docs/docs/quickstart.md`, `guide.md`  | Remove `OnceCondition` (6 places, including the "two ways to run a handler once" paragraph and the `once` pitfall). Show the `TypeError` of a bare function.             |
| `README.md`                            | Drop `OnceCondition` from the features. Replace the version table (its `coola` column is always "none" now) by the `python` column and a link to the changelog.          |
| `src/minevent/manager.py` docstrings   | Delete the "last triggered event name" sentence of `trigger_event` (F3). Add the `TypeError` to `add_event_handler` and the shape of the note to `trigger_event`.        |
| `CHANGELOG.md`                         | Under _Unreleased_: removal of `OnceCondition` and of the `minevent.subscription` module, the `TypeError`, the new note text, the lazy `inspect`. PR numbers.            |
| `tests/`, `dev/`, `.github/workflows/` | Section 8. `dev/benchmark.py` is deleted; no workflow refers to it.                                                                                                      |

---

## 6. Evidence

All on `main` at `335e29b`, Python 3.13.3, Apple laptop, minimum of repeated `timeit` runs, scripts
in the session scratchpad (not committed).

**Behaviour**

| Probe                                                                                  | `main`                                     | Target                   |
| -------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------ |
| F1: handler raises `ValueError`, one argument has a raising `repr`; exception received | `RuntimeError: repr boom`                  | `ValueError` with a note |
| F1: length of the note, handler with a 100,000-element list argument                   | 689,053 characters                         | under 100 characters     |
| F2: `add_event_handler("e", print)` then `trigger_event("e")`                          | accepted, `AttributeError` at the trigger  | `TypeError` at the add   |
| `once` consumed by a false condition, by a raising condition (note kept)               | consumed (`active` is `False`)             | unchanged                |
| `copy.deepcopy(EventManager())`                                                        | `TypeError: cannot pickle '_thread.RLock'` | unchanged, documented    |

**Speed** (prototype: only `handlers.py` changed as in section 3.3, in a copy of the package)

| Benchmark                                       |  `main` | Prototype | Note                                          |
| ----------------------------------------------- | ------: | --------: | --------------------------------------------- |
| awaitable check on `None`, alone                |  232 ns |     33 ns | `timeit`, both include the call of a lambda   |
| `trigger_event`, no handler                     |  293 ns |   not run | unchanged by the change                       |
| `trigger_event`, 1 handler                      |  706 ns |    463 ns | one session; run-to-run spread is about 40 ns |
| `import minevent` (`-X importtime`, cumulative) | 13.2 ms |    9.6 ms | 3 runs each, cold first run discarded         |
| disabled `logger.debug` call                    |   83 ns |     83 ns | kept (D6)                                     |

The 243 ns gain of the end-to-end row is larger than the 199 ns of the micro-benchmark, which is
within the noise of a laptop; the gate of section 8 re-measures on the real change. The other
findings are code removal or a new check at registration (one `isinstance`, outside the trigger).

---

## 7. Changes to reach the target state

One branch and one PR per row, branched from `main` (the rows are independent unless stated; rows 5
and 6 touch the same files as row 2 and 3, so merge them in this order). Every PR updates the
changelog with its number, has its tests, and keeps `ruff`, `ty` and 100% coverage.

| Step | Change                                                                                                                                                                                                                  | Breaking                                      |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| 1    | **Documents tell the truth** (F3, no code except docstrings): `trigger_event` docstring, `architecture.md` structure and complexity, README version table, properties table of section 1 copied into `architecture.md`. | no                                            |
| 2    | **Error note** (F1): `_describe`, `_add_error_note` uses it. Regression tests first (raising `repr`, huge argument), check they fail on `main` with `git stash push src`.                                               | note text                                     |
| 3    | **Validate the handler** (F2): `TypeError` in `add_event_handler`. Regression test fails on `main`.                                                                                                                     | yes (duck-typed objects are rejected)         |
| 4    | **Lazy `inspect`** (F4): `Awaitable`/`Coroutine` check, `import inspect` in `_accepted_keywords`. Package check: after `import minevent`, `inspect` is not in `sys.modules`.                                            | no                                            |
| 5    | **One module for the registration** (F5, F7): move `Subscription` into `manager.py`, delete `subscription.py` and `_snapshot`, merge `test_subscription.py` into `test_manager.py`, drop the `TYPE_CHECKING` import.    | yes (`minevent.subscription`, never released) |
| 6    | **Remove `OnceCondition`** (F6): class, export, tests, benchmark row, six documentation places, changelog.                                                                                                              | yes (never released)                          |
| 7    | **One benchmark mechanism** (F8): delete `dev/benchmark.py`; `CONTRIBUTING.md` says `inv test.benchmark`.                                                                                                               | no                                            |

Steps 1 and 4 to 7 are safe to merge alone. Steps 2 and 3 change visible behaviour and go in the
same release as 5 and 6 so that the migration table of section 4 is written once.

---

## 8. Tests and gates

New or changed tests (the other tests of the first review stay):

- **Note (P7, F1).** The exception is the same object; `__notes__` has the event and the callable
  name for a function, a bound method, a `functools.partial`, a callable instance and a custom
  `BaseEventHandler`; a handler argument with a raising `repr` still surfaces the original
  exception; a 100,000-element argument gives a short note. `_describe` is tested on its own, as
  `CLAUDE.md` asks for private functions. Whole-note assertion on the exact string.
- **Validation (P3, F2).** A function, `None`, a string and a class (not an instance) raise
  `TypeError` with `match`; the message names the type; a custom `BaseEventHandler` is accepted.
  For the same call in `atrigger_event` nothing changes.
- **Import (P11, F4).** `tests/package_checks.py`: `inspect` and `importlib.metadata` are not in
  `sys.modules` after `import minevent` (run in a subprocess on the built wheel). `filter_payload=True`
  still works (it imports `inspect` on first use).
- **Awaitable.** A coroutine function raises `TypeError` in `handle` and is closed (no
  `RuntimeWarning`); an `asyncio.Future`/object with `__await__` raises `TypeError`; `None` and
  ordinary values are fine; `ahandle` awaits all of them.
- **Subscription after the merge (P4).** The tests of `test_subscription.py` move unchanged; the
  regression test of the duplicate registration stays.
- **Whole-output tests.** `repr` of the manager, the handler and the subscription (exact strings),
  `get_subscriptions` (exact tuple).
- **Threads** (`tests/integration/`): unchanged; they must pass after step 5 with no edit but the
  import.
- **Doctests.** Source docstrings and the Markdown pages (`inv test.doctest`) after steps 1 and 6.
- **Benchmark gate.** `inv test.benchmark` before and after steps 2 to 5; a row more than 10% slower
  is explained in the PR. The nightly workflow fails at 50% on a median.
- **Coverage.** 100% line and branch on `src/minevent`, no `# pragma: no cover`.
- **Lint and types.** `ruff check`, `ruff format --check`, `ty check` on `src` and `tests`.

---

## 9. Decisions for the maintainers

Decisions of the first review (snapshot dispatch, `once` consumed on a false condition or a raising
handler, sequential async, no lock in conditions, keep `handler_args`/`handler_kwargs`, one-line
`repr`s, lazy `__version__`, `get_subscriptions`) are settled and not reopened.

| #   | Question                                                                             | Recommendation                                                                                                                                                                                                                                                                                                     |
| --- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | What does the error note contain?                                                    | **Event and callable name.** A note that can raise or fill a log defeats the purpose of fail-fast. Alternative: keep `repr(handler)` and guard it with `try`/`except` and a length cap (more code, still noisy).                                                                                                   |
| D2  | A bare function in `add_event_handler`: reject, or wrap it in `EventHandler`?        | **Reject (`TypeError`).** Two accepted types are two ways to do one thing, and `EventHandler(func)` is short. `manager.on(event)` already covers the bare-function case. Alternative: wrap automatically; then `add_event_handler("e", print)` works and `Subscription.event_handler` is always an `EventHandler`. |
| D3  | Merge `Subscription` into `manager.py`?                                              | **Yes.** One concept, one file, no cross-module private access, no cycle. Alternative: keep two files and give `Subscription` a method the manager calls (`_deactivate`), which is still a private call across modules.                                                                                            |
| D4  | Remove `OnceCondition`?                                                              | **Yes.** `once=True` is atomic and removes the dead registration; `OnceCondition` is neither, and the docs already apologise for having both.                                                                                                                                                                      |
| D5  | Lazy `inspect` and the `Awaitable` check?                                            | **Yes.** About 3.6 ms of import and 200 ns per handler call for a rule that `CLAUDE.md` already states. The only difference is the legacy generator-based coroutine (section 3.3).                                                                                                                                 |
| D6  | Keep the `logger.debug` calls, including the one in each trigger (12%)?              | **Keep.** It is the only way to see that an event with no handler fired, and it is the documented debugging tool. Alternative: remove the trigger line and keep the three on the cold paths (registration, removal, clear).                                                                                        |
| D7  | Delete `dev/benchmark.py`; keep `dev/benchmark_trend.py` (131 lines + 108 of tests)? | **Delete the script, keep the trend.** The suite covers every row of the script. The trend page is what makes the nightly artifact readable and prunes it; replacing it needs a retention rule in the workflow, which is as much code. Revisit if nobody reads the nightly summary.                                |

---

## 10. Not covered

- **Priorities, wildcards, hierarchical events, event objects.** Non-goals of the architecture page.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). Worth a separate design
  if users ask; it does not change the runtime.
- **Weak references / auto-unsubscribe, collecting errors (`ExceptionGroup`), cross-process or
  persistent events, offloading blocking handlers to a thread.** Non-goals, unchanged.
- **Free-threaded safety of conditions.** Documented limit (first review, D8).
- **`Subscription` built by hand.** `Subscription(manager, ...)` then `remove()` raises `KeyError`
  **[verified]**; the constructor is documented as internal, and Python cannot make it private.
- **Copy and pickle of the manager.** Documented limit, section 1.
- **Repository tooling.** 26 workflows, the shared `.make/` directory and two task runners
  (`invoke` and `make`) are large for a 1,300-line package. They are shared with other projects, so
  they are outside this review; the only item taken is the duplicate benchmark script (F8).
- **The `Tracer` test helper.** The first review proposed `unittest.mock`; the maintainers kept the
  helper and `CLAUDE.md` now describes it ("traced handler"). Not reopened.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate, the gate is the behaviour of
sections 1 and 8, not the size.

| Module                                       | Lines today | Expected after | Why                                                                               |
| -------------------------------------------- | ----------: | -------------: | --------------------------------------------------------------------------------- |
| `conditions.py`                              |         231 |           ~185 | `OnceCondition` (class, docstring, doctest)                                       |
| `handlers.py`                                |         390 |           ~395 | `Awaitable` check and a local import: same size                                   |
| `manager.py` + `subscription.py`             |   466 + 146 |           ~590 | `_snapshot` gone, one header and imports, `_describe` and the handler check added |
| `__init__.py`                                |          49 |            ~46 | one export fewer                                                                  |
| **`src`**                                    |   **1,282** |     **~1,215** |                                                                                   |
| `src` statements                             |         276 |           ~268 |                                                                                   |
| `tests/` (unit, integration, package checks) |       2,661 |         ~2,600 | `OnceCondition` and `_snapshot` tests out, note, validation and import tests in   |
| `tests/benchmarks/`                          |         419 |           ~410 | `OnceCondition` row                                                               |
| `dev/`                                       |         213 |           ~131 | `benchmark.py` out                                                                |
| `docs/docs` (without `refs/`)                |       1,505 |         ~1,470 | `OnceCondition` paragraphs, duplicated properties                                 |
| Runtime dependencies                         |           0 |              0 |                                                                                   |
| `import minevent`                            |     13.2 ms |        ~9.6 ms | lazy `inspect`                                                                    |
