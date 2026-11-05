# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`06a8292`, 2026-11-05), and proposes the smallest set of changes that makes every property true.
It replaces the second version of this review. That version is merged (steps 1 to 7: documents,
error note, validated handler, `Awaitable` check, `Subscription` in `manager.py`, no
`OnceCondition`, one benchmark mechanism), so this version starts from the result and only looks at
what is left. The package is small (1,299 lines, 268 statements, 0 dependencies) and every gate is
green, so the remaining work is short: **one scaling defect, one unbounded-growth defect, one API
gap, and documents that drifted again**. Breaking changes are accepted (the README says the API is
unstable before 1.0), but this version needs almost none: the design is at its target, and the
review says so instead of inventing work.

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, one behaviour per test).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.13.3,
Apple laptop, scripts kept outside the repository) or **[reading]** (from the code or the
documents). Nothing in `src`, `tests` or `docs` was changed by this review.

**Baseline on `main`** [verified]: `ruff check`, `ruff format --check` and `ty check` clean; 305
unit and integration tests pass in 2 s with 100% line and branch coverage (268 statements, 52
branches); 22 source doctests pass; the doctests of `README.md` and of the six pages of `docs/docs`
pass (`python -m doctest`, as `inv test.doctest` runs them). The items below are what this baseline
does not catch.

## Constraints

1. **Simple and easy to maintain.** Fewer concepts, one way to do each thing. A change that adds
   code must remove a defect or a duplicate; a change that only adds a feature is a decision (D3),
   not a default.
2. **Breaking changes are accepted.** Migration notes go in `CHANGELOG.md`, with the PR number.
3. **No slower than today.** Benchmark gate in section 8: a row more than 10% slower needs a reason.
4. **Documented guarantees are true and tested.** Every property of section 1 names the test that
   enforces it; a property without a test is a finding.
5. **No runtime dependency, heavy imports lazy.** Standard library only; `importlib.metadata` is
   not imported until `__version__` is read. `inspect` stays a module-level import by decision of
   the maintainers (PR #749), so it is not a finding.
6. **Python `>=3.11`.** `BaseException.add_note` and `typing.Self` are used.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _event handler_, _event manager_) plus the `Subscription`
that a registration returns and the plain-callable _conditions_. These are the rules. Each design
choice below exists to make one of them true **by construction** instead of by discipline. The
"Test" column names the test that enforces the property today (all verified to exist); "gap" marks a
clause with no test.

| #   | Property                 | Statement                                                                                                                                                                                                                                                                         | Test                                                                                                                                                                          |
| --- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | Small surface            | Three concepts and plain callables. Seven exported names and `__version__`. `EventManager` has 9 public members.                                                                                                                                                                  | `__all__` is reviewed in each PR; no test (trivial structure, `CLAUDE.md`)                                                                                                    |
| P2  | Events are strings       | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                | `..._event_must_be_str`, `..._unknown_event_does_not_register_it`, `get_subscriptions_does_not_create_event`                                                                  |
| P3  | Validated at the door    | A wrong type raises `TypeError` **in the call that receives it**: the event, the handler of `add_event_handler`, the callable, the arguments and the condition of `EventHandler`.                                                                                                 | `..._event_handler_must_be_event_handler`, `..._invalid_event_handler_is_not_registered`, `test_event_handler_incorrect_handler`, `..._incorrect_handler_args`, `..._condition_incorrect_type` |
| P4  | Registration identity    | `add_event_handler` returns a new `Subscription` every time; the same handler can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`.                                                                              | `test_subscription_remove_*`, `..._duplicate_event_handlers`                                                                                                        |
| P5  | Registration order       | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                       | `get_subscriptions_keeps_order`, `atrigger_event_mixes_sync_and_async_in_order`                                                                                                |
| P6  | Snapshot dispatch        | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                                                          | `..._added_during_dispatch_*`, `..._removed_during_dispatch_*`, `atrigger_event_snapshot`                                                                                     |
| P7  | Fail-fast with context   | An exception of a handler propagates **unchanged** (same object, same type); the remaining handlers are skipped. It carries a note with the event and the handler callable, **once per distinct pair**. Building the note never runs the `repr` of user data.                     | `..._raises_same_exception_type_and_object`, `..._adds_note`, `..._note_ignores_repr_of_arguments`, `..._note_is_short_for_large_arguments`; **gap: a reused exception (F2)**  |
| P8  | `once` is at-most-once   | A `once` registration is removed **before** its handler is called, by an atomic claim: it runs at most once whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                                                              | `test_once_handler_runs_once_when_snapshots_taken_before_dispatch` (barrier), `..._once_removed_when_condition_false`, `..._once_handler_raises`                              |
| P9  | Synchronous by default   | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop.                                                   | `test_event_handler_handle_coroutine_raises`, `..._is_closed`, `test_manager_async.py`                                                                                        |
| P10 | Thread-safe registry     | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run **outside** the lock, so a handler can use the manager.                                                                                                                    | `tests/integration/test_manager_threads.py`, `..._trigger_event_runs_handler_without_lock`                                                                                    |
| P11 | No hidden state          | No global manager, no discovery, no side effect of a read. Zero runtime dependencies. `import minevent` does not import `importlib.metadata`.                                                                                                                                     | `tests/package_checks.py` (`check_no_third_party_import`, `check_lazy_imports`)                                                                                                |
| P12 | Payload is data          | `trigger_event(event, /, **payload)` passes the payload to every handler as keyword arguments, after `handler_kwargs`. Any key is allowed (`event`, `self`). With `filter_payload=True` only the keys the signature accepts are passed.                                           | `..._payload_with_event_and_self_keys`, `test_event_handler_filter_payload_*`, `..._payload_conflicts_with_handler_kwargs`                                                    |
| P13 | Conditions are callables | A condition is a `Callable[[], bool]`, called once per trigger and per handler, before the handler. The built-in conditions keep per-instance state; sharing an instance shares the state. There is **one** way to run a handler once (`once=True`).                              | `test_event_handler_condition_*`, `test_conditions.py`                                                                                                                        |
| P14 | Typed                    | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                | `ty` in `ci-type-checking.yaml`                                                                                                                                               |
| P15 | Fast and linear          | A trigger of one handler costs about 0.46 µs, each extra handler about 0.15 µs, a registration plus its removal about 0.9 µs. Registering _k_ handlers and removing them in any order costs O(_k_) in total. Not slower than today.                                              | `tests/benchmarks/` (nightly gate at 50%); **gap: no row removes many registrations (F1)**                                                                                    |

### Not guaranteed, and documented as such

- **Order across threads.** Two threads that trigger the same event run the handlers concurrently,
  in no defined interleaving. A handler that shares state must protect it.
- **State of conditions under threads.** `PeriodicCondition` and `AfterNCondition` update a counter
  without a lock (decision D8 of the first review, unchanged).
- **A handler removed while a trigger is running** still runs in that trigger (P6). After `remove()`
  returns, the next trigger does not run it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **Copy and pickle.** An `EventManager` holds a lock: `copy.deepcopy` and `pickle` raise
  `TypeError` (`cannot pickle '_thread.RLock'`) **[verified]**. Create a new manager instead.
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  list, `Subscription`, manager): `del manager` does not free it until the garbage collector runs,
  while an empty manager is freed at once **[verified]**. Call `reset()` to release the handlers
  at a known point (the guide already says so).

---

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Status         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| F1  | **P15 is false: removing a registration is O(n), so churn is quadratic.** The registry stores a `list` per event and `_remove` calls `list.remove`, which scans from the front and compares. Removing 10,000 registrations of one event in last-in first-out order (the order of nested `with manager.add_event_handler(...)` blocks) takes **420 ms**; 50,000 take **10.6 s** (the list is 10 times longer, the time 25 times). A long-running service that subscribes per request and unsubscribes at the end pays it. `architecture.md` documents it as a feature ("`O(n)` removal of a registration").                                                                                                    | **[verified]** |
| F2  | **P7 is false for a reused exception: the notes grow without bound.** `_add_error_note` adds a note on every propagation. An exception **instance** raised again (a module-level `STOP = StopTraining()`) has 1,000 notes after 1,000 triggers. A handler that retriggers its own event ends in a `RecursionError` with **249 notes** (11,703 characters) that all say the same thing.                                                                                                                                                                                                                                                                                                                  | **[verified]** |
| F3  | **The documents drifted again.** The performance numbers were measured before PR #749: `guide.md:253` and `faq.md:87` say "about 0.7 µs" for one handler and "about 0.4 µs for each additional handler"; `main` measures 0.46 µs and 0.15 µs (1 handler 463 ns, 10 handlers 1,830 ns, 100 handlers 15,564 ns). `README.md:144` keeps the version table with a `coola` column that says "none" for `main`, in a package that has no dependency (the sentence above it still talks about "supported dependencies", and the README then says "install only some specific dependencies"). `architecture.md` lists 10 properties; P1, P3, P7 (the note), P13, P14 and P15 of section 1 are in no document.                  | **[verified]** |
| F4  | **`on` cannot express what the guide recommends.** The documented way to let handlers with different needs share an event is `filter_payload=True`, and the documented way to run a handler sometimes is a condition. The decorator takes neither: `guide.md` says "use `add_event_handler` if the handler needs arguments or a condition". The most common handler of a training loop (a function that wants `epoch` out of a payload that also has `loss` and `lr`) cannot use the short form, so there are two registration paths with different capabilities.                                                                                                                                         | **[reading]**  |
| F5  | **A hand-built `Subscription` raises `KeyError` from `remove()`.** `Subscription(manager, "e", handler).remove()` finds `active == True` and then indexes `self._subscriptions["e"]`. The constructor is documented as internal, but the failure is a bare `KeyError: 'e'`. With the registry of F1 the check "is it registered" is one lookup and returns `False`, so the failure disappears at no cost.                                                                                                                                                                                                                                                                                              | **[verified]** |
| F6  | **`inv test.doctest` needs `python` on the `PATH`.** `invoke_tasklib` runs `python -m pytest ...` and `python -m doctest ...`; the environment has only `.venv/bin/python` (`CLAUDE.md`), so `.venv/bin/inv test.doctest` fails with `python: command not found` **[verified]**. The markdown pages are not checked by any other command, so an agent that follows `CLAUDE.md` literally never runs them.                                                                                                                                                                                                                                                                                              | **[verified]** |

### Measured and kept

- **Debug logging.** A disabled `logger.debug` costs 83 ns, about 18% of a one-handler trigger. It
  is what tells a user "my handler does not run" that the event was fired at all (`guide.md`,
  Debug). Kept (D6 of the second review).
- **`once` consumed by a false or a raising condition.** Works as P8 says. The reading "run at the
  first `True`" is a two-line condition, shown in the quickstart. Kept (settled).
- **`filter_payload` shadowing.** `EventHandler(f, [1], filter_payload=True)` with `def f(a, b)`
  and a payload that has `a` raises `TypeError: f() got multiple values for argument 'a'`, and a
  payload key that is also in `handler_kwargs` raises the same kind of error **[verified]**. This is
  the documented conflict rule (guide: "A key that is in both `handler_kwargs` and the payload
  raises a `TypeError`"); the message names the function and the argument. Kept.
- **The note names `dumps`, not `json.dumps`.** The traceback above the note already shows the file
  and the line, and the module would make every note longer. Kept.
- **A condition that raises** gets the note "raised by <handler> ..." although the handler did not
  run. The exception type and the traceback say where it came from. Kept.
- **Subclasses of `str` as events**, and unhashable events in `in`: a `str` subclass is accepted and
  found; `[] in manager` raises the `TypeError` of `dict`. Kept.
- **A cancelled `atrigger_event`** leaves a consumed `once` registration inactive (cancel is a
  `BaseException`: no note, the claim already happened, P8) **[verified]**.
- **`reset()` called by a handler** during a trigger: the rest of the snapshot still runs (P6) and
  `len(manager)` is 0 afterwards **[verified]**.

### What already works and must not regress

- Snapshot dispatch with the handlers outside the lock (P6, P10), `RLock` so a handler can use the
  manager, and `once` claimed atomically.
- `event` and `self` as payload keys (`event` is positional-only), the awaitable check in `handle`
  (a coroutine is closed, so no `RuntimeWarning`), `filter_payload`, `handler_kwargs` copied,
  `str` and `bytes` `handler_args` rejected, array-like `handler_args` accepted.
- `Subscription` identity by default: `list.remove(sub)` and `dict[sub]` use that record.
- Fail-fast and the non-goals (event objects, priorities, weak references, collecting errors).
- The test suite follows `CLAUDE.md`: no local import, no sleep in `tests/unit`, every
  `pytest.raises` has a `match`. Of 277 test functions, 19 have more than one `assert`; 17 are the
  allowed cases (the `call_count`, `args` and `kwargs` of a traced handler, the count and uniqueness
  of a thread test) and 2 are borderline, listed in section 8 **[verified]**.

---

## 3. Architecture

```text
EventManager ──registry──▶ {event: {Subscription: None, ...}}      insertion order = run order
     │                          event, event_handler, once, active
     │ trigger_event(event, /, **payload)
     ▼
for sub in get_subscriptions(event):        # tuple(dict): a snapshot, under the lock
    if sub.once and not _remove(sub):       # atomic claim (P8)
        continue
    sub.event_handler.handle(**payload)     # outside the lock
         │
         ▼
EventHandler.handle ──▶ condition() ──▶ filter payload ──▶ handler(*args, **kwargs, **payload)
```

The design is kept: three modules, no cycle, no dependency. It is already the smallest that has
every property.

| Module          | Contains                                                     | Lines |
| --------------- | ------------------------------------------------------------ | ----: |
| `conditions.py` | `Condition` protocol, `PeriodicCondition`, `AfterNCondition` |   204 |
| `handlers.py`   | `BaseEventHandler`, `EventHandler`                           |   391 |
| `manager.py`    | `EventManager`, `Subscription`                               |   649 |

### 3.1 The registry is an ordered set (F1, F5)

A `dict` is an insertion-ordered set. `{event: {subscription: None}}` keeps the registration order
(P5), uses the identity hash that `Subscription` already has (P4), and removes in O(1):

```python
# EventManager.__init__
self._subscriptions: dict[str, dict[Subscription, None]] = {}

# add_event_handler
with self._lock:
    self._subscriptions.setdefault(event, {})[subscription] = None

# get_subscriptions
with self._lock:
    return tuple(self._subscriptions.get(event, ()))  # iterates the keys


# _remove
def _remove(self, subscription: Subscription) -> bool:
    with self._lock:
        subs = self._subscriptions.get(subscription.event)
        if subs is None or subscription not in subs:
            return False
        subscription._active = False
        del subs[subscription]
        if not subs:
            del self._subscriptions[subscription.event]
    logger.debug("Removed %s in '%s' event", subscription.event_handler, subscription.event)
    return True
```

`clear_event`, `reset`, `__len__` and `__repr__` do not change (they iterate the values or the
keys). The diff is five lines. `Subscription` must stay hashable by identity: it defines no
`__eq__`, and a test pins it (as `test_event_handler_hashable` does for handlers). A hand-built
`Subscription` that was never registered now returns `False` from `remove()` instead of raising
`KeyError` (F5).

A prototype of exactly this change on a copy of the package passes the 305 existing tests with no
edit and gives the numbers of section 6.

### 3.2 One note per distinct pair (F2)

```python
def _add_error_note(exc: Exception, event: str, event_handler: BaseEventHandler) -> None:
    note = f"raised by {_describe(event_handler)} while handling the event {event!r}"
    if note not in getattr(exc, "__notes__", ()):
        exc.add_note(note)
```

The check runs only on the exception path. Nested triggers of **different** events or handlers keep
one note each (a handler of `a` that triggers `b`, whose handler raises, gives two notes: the chain
is the information); the same pair repeated, by a reused instance or by a recursion, is one note.
P7 says "once per distinct pair".

### 3.3 `on` takes the options of the handler (F4)

```python
def on(
    self,
    event: str,
    *,
    once: bool = False,
    condition: Condition | None = None,
    filter_payload: bool = False,
) -> Callable[[_F], _F]:
    _check_event(event)

    def decorator(func: _F) -> _F:
        handler = EventHandler(func, condition=condition, filter_payload=filter_payload)
        self.add_event_handler(event, handler, once=once)
        return func

    return decorator
```

```python
@manager.on("epoch_end", filter_payload=True)
def log_epoch(epoch: int) -> None: ...
```

`handler_args` and `handler_kwargs` stay out: a decorated function is called with the payload, and
`functools.partial` or `EventHandler` covers the rest. The decorator still returns the function and
not the `Subscription` (it is a decorator); a function that must be unsubscribed uses
`add_event_handler`. This is a decision (D3), because it adds a feature to remove a documented
workaround.

---

## 4. Public API after the change

```python
# minevent/__init__.py: unchanged
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

| Signature                                                                       | Change                                  |
| ------------------------------------------------------------------------------- | --------------------------------------- |
| `EventManager.on(event, *, once=False, condition=None, filter_payload=False)`   | two keyword-only options (D3)           |
| `Subscription.remove() -> bool`                                                 | `False` instead of `KeyError` (F5)      |
| every other signature, every exported name                                      | unchanged                               |

### Migration

| Code                                                                     | After                                                           |
| ------------------------------------------------------------------------ | --------------------------------------------------------------- |
| Code reading `exc.__notes__` and expecting one note per propagation     | one note per distinct pair                                      |

Nothing else breaks. There is no release between the second review and this one, so the changelog
entries stay under _Unreleased_.

---

## 5. Dependents

| Place                                 | Change                                                                                                                                                                                                                      |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/docs/architecture.md`           | Replace the "Properties" bullets by the table of section 1 (same ids, without the "Test" column). Fix the structure block (`{event: {subscription: None}}`) and the complexity list (`O(1)` removal). Add the clause of P7. |
| `docs/docs/guide.md`, `faq.md`        | Performance numbers (F3): 0.5 µs for one handler, 0.15 µs per extra handler. Replace "use `add_event_handler` if the handler needs arguments or a condition" by the options of `on` (D3). Show `filter_payload` with `on`.   |
| `README.md`                           | Replace the version table by the `python` column and a link to the changelog; drop "supported dependencies" from the sentence above it. Also the "install only some specific dependencies" sentence.                                |
| `CLAUDE.md`                           | One line: run the tasks as `PATH=.venv/bin:$PATH .venv/bin/inv test.doctest` (F6), so the markdown pages are checked.                                                                                                       |
| `src/minevent/manager.py` docstrings  | `on` (new options, `Args:`, example), `_add_error_note` (the dedupe), `Subscription.remove` (never raises), `EventManager` (structure, no cost claim).                                                                      |
| `CHANGELOG.md`                        | Under _Unreleased_: O(1) removal, one note per distinct pair, `on` options. PR numbers.                                                                                                                                     |
| `tests/benchmarks/`                   | Section 8: one row that removes many registrations in reverse order.                                                                                                                                                        |

---

## 6. Evidence

All on `main` at `06a8292`, Python 3.13.3, Apple laptop, minimum of 5 `timeit` repeats, scripts in
the session scratchpad (not committed).

**Behaviour**

| Probe                                                                              | `main`                                           | Target                          |
| ---------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------- |
| F1: remove 10,000 registrations of one event, last-in first-out                    | 420 ms                                           | 3.3 ms (prototype)              |
| F1: remove 50,000 registrations, same order                                        | 10,605 ms                                        | 16.3 ms (prototype)             |
| F2: raise one exception instance in 1,000 triggers, `len(exc.__notes__)`           | 1,000                                            | 1                               |
| F2: handler that retriggers its event, `len(RecursionError.__notes__)`             | 249 notes, 11,703 characters                     | 1 note                          |
| F5: `Subscription(EventManager(), "e", handler).remove()`                         | `KeyError: 'e'`                                  | `False`                         |
| F6: `.venv/bin/inv test.doctest`                                                   | `python: command not found`                      | runs with `PATH` set (22 pass)  |
| manager with one registration, `del manager`, `gc` disabled                        | not freed (cycle); freed after `gc.collect()`    | unchanged, documented           |
| `copy.deepcopy(EventManager())`                                                    | `TypeError: cannot pickle '_thread.RLock'`       | unchanged, documented           |

**Speed** (prototype: only `manager.py` changed as in section 3.1, in a copy of the package; the 305
tests pass against it)

| Benchmark                                       |  `main` | Prototype | Note                                           |
| ----------------------------------------------- | ------: | --------: | ---------------------------------------------- |
| `trigger_event`, no handler                     |  288 ns |   not run | unchanged by the change                        |
| `trigger_event`, 1 handler                      |  457 ns |    488 ns | run-to-run spread is about 40 ns               |
| `trigger_event`, 10 handlers                    | 1,857 ns |  1,876 ns | same                                           |
| `trigger_event`, 100 handlers                   | 15,564 ns |   not run | 0.15 µs per handler: the number for the docs   |
| `add_event_handler` then `remove()`             |  925 ns |    939 ns | a dict insert replaces a list append           |
| `import minevent` (`-X importtime`, cumulative) |   13 ms |    13 ms | `inspect` is 6.6 ms of it; kept by decision    |
| disabled `logger.debug` call                    |   83 ns |     83 ns | kept                                           |

The +31 ns of the one-handler row is inside the spread of a laptop; the gate of section 8
re-measures on the real change and the change is rejected if a trigger row is more than 10% slower.
The registry is read by `tuple(dict)` instead of `tuple(list)`: both are a C loop over the same
number of entries.

---

## 7. Changes to reach the target state

One branch and one PR per row, branched from `main` (the rows are independent; stack them in this
order if they are in flight together, as the second review did). Every PR updates the changelog with
its number, has its tests, and keeps `ruff`, `ty` and 100% coverage.

| Step | Change                                                                                                                                                                                                                                              | Breaking                       |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| 1    | **Documents tell the truth** (F3, F6, no code except docstrings): performance numbers, README and `get_started.md` dependency wording, the properties table in `architecture.md` (P7 and P15 as written in section 1), the `PATH` line in `CLAUDE.md`. | no                             |
| 2    | **Ordered-set registry** (F1, F5): section 3.1, benchmark row first (it must show the quadratic cost on `main`), then the change; `architecture.md` structure and complexity; the `remove()` docstring.                                              | no                             |
| 3    | **One note per distinct pair** (F2): section 3.2. Regression tests first (reused instance, self-retrigger), check they fail on `main` with `git stash push src`.                                                                                  | notes of a reused exception    |
| 4    | **`on` options** (F4, D3): section 3.3, docstring example, guide and quickstart text. Skip this step if D3 is declined.                                                                                                                            | no                             |

**Status.** Stacked PRs, each on the previous one: none opened yet.

| Step | PR |
| ---- | -- |
| 1    |    |
| 2    |    |
| 3    |    |
| 4    |    |

All four steps are safe to merge alone and in any order. Steps 2 and 3 change no signature.

---

## 8. Tests and gates

New or changed tests (the existing 305 stay). Each is one behaviour, with `match` on every
`pytest.raises`, and the regression tests are checked to fail on `main`.

- **Registry (P4, P5, F1, F5).**
  - removing the middle registration keeps the order of the others (`get_subscriptions` against a
    literal tuple);
  - removing the first and the last of three keeps the middle one;
  - registering one handler three times and removing the second subscription leaves the first and
    the third, in that order;
  - `Subscription` is hashable by identity and two subscriptions of the same handler are different
    keys;
  - a hand-built `Subscription(manager, "e", handler).remove()` returns `False` (regression for F5);
  - the event disappears from `manager.events` when its last registration is removed (exists).
- **Notes (P7, F2).**
  - the same exception instance raised through three triggers has one note (regression);
  - a handler that retriggers its own event ends in a `RecursionError` with one note (regression);
  - a handler of `a` that triggers `b`, whose handler raises, gives two notes, in that order, with
    the whole `__notes__` asserted against a literal list;
  - `_add_error_note` is tested on its own: first call adds, second identical call does not, a call
    with another event adds (`CLAUDE.md`: private functions have tests).
- **`on` options (D3).** `filter_payload=True` passes only the accepted keys; `condition=` is
  evaluated before the handler; both reach the `EventHandler` registered (`get_subscriptions` then
  `.event_handler.condition` and `.filter_payload`); the function is returned unchanged; `once=True`
  still works with them. The same on `atrigger_event` with a coroutine function.
- **Integration** (`tests/integration/`): the thread tests pass with no edit. Add one that removes
  from several threads the registrations that other threads added (`run_threads`, lock around the
  shared list, docstring "Test that ...") to exercise `_remove` on a dict under contention.
- **Benchmark gate.** New row `test_subscription_remove_many_lifo_benchmark`: register 10,000
  handlers on one event, remove them in reverse order. `inv test.benchmark` before and after steps
  2 to 4; a trigger row more than 10% slower is explained in the PR; the new row must improve by
  more than 10 times (420 ms to about 3 ms). The nightly workflow fails at 50% on a median.
- **Doctests.** `PATH=.venv/bin:$PATH .venv/bin/inv test.doctest` after steps 1, 2 and 4: source and
  the markdown files.
- **Coverage.** 100% line and branch on `src/minevent`, no `# pragma: no cover`.
- **Lint and types.** `ruff check`, `ruff format --check`, `ty check` on `src` and `tests`.

**Tests that are borderline for `CLAUDE.md` today** (of the 19 functions with more than one
`assert`, 17 are the allowed state-of-one-object and thread cases) [verified]. Two could be split in a
separate `test` PR with no `src` change; it is not a prerequisite of the steps above:

| Test                                                          | Why                                                                                       |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `test_load_runs_skips_old_results_and_keeps_the_file` (dev)   | two behaviours in one name: skips the old results, keeps the file                         |
| `test_event_manager_trigger_event_handler_raises_adds_note`   | a `pytest.raises` and an `assert` on the note; the rule is one or the other (low value)   |

----------------------------------------------------------------- | ----------------------------------------- |
| `test_event_handler_handle_payload` (`test_handlers.py`)          | 2                                         |
| `test_event_handler_handle_payload_after_handler_args_and_kwargs` | 2                                         |
| `test_event_handler_condition_handle_1`, `..._10` (`test_handlers.py`) | 3 each (counts and recorded calls)   |
| `test_load_runs_skips_old_results_and_keeps_the_file`             | 2                                         |

(`test_event_handler_handle_*` with 3 asserts record `call_count`, `args` and `kwargs` of a traced
handler: the exception that `CLAUDE.md` allows.)

---

## 9. Decisions for the maintainers

Decisions of the first and second reviews (snapshot dispatch, `once` consumed on a false condition or
a raising handler, sequential async, no lock in conditions, `handler_args`/`handler_kwargs` kept,
one-line `repr`s, lazy `__version__`, `get_subscriptions`, bare function rejected by
`add_event_handler`, note without `repr`, `inspect` imported at module level, the `Tracer` helper,
`logger.debug` kept, `dev/benchmark_trend.py` kept) are settled and not reopened.

| #   | Question                                                                       | Recommendation                                                                                                                                                                                                                                                                                                                                                 |
| --- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Registry: `list` per event or `dict` as an ordered set?                        | **`dict`.** O(1) removal, same order, same size, one line simpler in `_remove`, and it deletes the `KeyError` of a hand-built subscription. Alternative: keep the list and document the O(n) removal (already documented); acceptable below about 1,000 registrations per event (4.4 ms for 1,000 removals), wrong for a service that subscribes per request.        |
| D2  | Repeated notes: dedupe, cap the count, or keep only the first?                 | **Dedupe the identical text.** It is one `in` on the exception path, keeps the chain of nested triggers, and needs no constant. Alternative: a cap (for example 5 notes) is a magic number; "only the first" loses the outer events.                                                                                                                            |
| D3  | `on` forwards `condition` and `filter_payload`?                                | **Yes.** `filter_payload` is the documented way to share an event, so the short form should reach it; two keyword-only options, no new concept, and it deletes a sentence of the guide. Alternative: leave `on` minimal ("sugar for a handler with no options") and keep the sentence; then there are two paths with different capabilities, as today.            |
| D4  | Should a condition receive the payload (`Callable[..., bool]`)?                | **No.** `epoch % 5 == 0` is a check on data; the handler has the payload and can return early, and a condition with arguments needs the `filter_payload` machinery too. A condition is "when", the handler is "what". Revisit if users ask; it would be a breaking change of the protocol (`Condition.__call__(**payload)`).                                    |
| D5  | Break the manager/subscription cycle (weak reference in `Subscription`)?       | **No.** The cost is a freed-by-GC manager, only when it holds registrations; a weak reference is a non-goal of the architecture page and adds a branch to every `remove()`. `reset()` is the documented release point.                                                                                                                                        |
| D6  | Share the dispatch loop of `trigger_event` and `atrigger_event` in a helper?   | **No.** The two loops differ in the `await` and are 8 lines each; the second review removed `_snapshot` for the same reason. A generator that yields the claimed subscriptions adds an object per trigger to save about 4 lines.                                                                                                                                |

---

## 10. Not covered

- **Priorities, wildcards, hierarchical events, event objects.** Non-goals of the architecture page.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). Worth a separate design
  if users ask; it does not change the runtime.
- **Weak references / auto-unsubscribe, collecting errors (`ExceptionGroup`), cross-process or
  persistent events, offloading blocking handlers to a thread.** Non-goals, unchanged.
- **Free-threaded safety of conditions.** Documented limit (first review, D8).
- **Handlers as plain callables** (drop `EventHandler`, or let `add_event_handler` wrap a function).
  It would remove a concept the documents define; settled by D2 of the second review, and F4 closes
  most of the verbosity through `on`.
- **The `mkdocs` build.** The `docs` dependency group is not installed here, so the generated
  reference (`refs/index.md` documents `minevent`, `refs/manager.md` documents `minevent.manager`,
  so `EventManager` may appear twice) was not rendered. Check it with `mkdocs build --strict` when
  step 1 is reviewed.
- **Repository tooling.** 26 workflows, the shared `.make/` directory and two task runners
  (`invoke` and `make`) are large for a 1,300-line package. They are shared with other projects, so
  they are outside this review.
- **`tests/unit/test_utils.py`** tests a test helper (`tests/unit/utils.py`), not a module of `src`,
  so it does not mirror the source tree. The maintainers kept the helper; not reopened.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate, the gate is the behaviour of sections 1
and 8, not the size.

| Module                                       | Lines today | Expected after | Why                                                               |
| -------------------------------------------- | ----------: | -------------: | ----------------------------------------------------------------- |
| `conditions.py`                              |         204 |            204 | unchanged                                                         |
| `handlers.py`                                |         391 |            391 | unchanged                                                         |
| `manager.py`                                 |         649 |           ~665 | `on` options and docstring (+14), dedupe (+2), `_remove` (-1)     |
| `__init__.py`                                |          55 |             55 | unchanged                                                         |
| **`src`**                                    |   **1,299** |     **~1,315** |                                                                   |
| `src` statements                             |         268 |           ~272 | `on` forwards two options, dedupe adds one branch                 |
| `tests/` (unit, integration, package checks) |       2,730 |         ~2,830 | registry, notes and `on` tests                                    |
| `tests/benchmarks/`                          |         416 |           ~430 | one row                                                           |
| `docs/docs`                                  |       1,539 |         ~1,545 | properties table in, duplicated sentences out                     |
| Runtime dependencies                         |           0 |              0 |                                                                   |
| `import minevent`                            |       13 ms |          ~13 ms | unchanged                                                         |
