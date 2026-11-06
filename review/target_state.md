# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`df13132`, 2026-11-06), and proposes the smallest set of changes that makes every property true.
It replaces the third version of this review. That version is merged (#764 to #767: documents,
ordered-set registry, one note per distinct pair, `on` options), so this version starts from the
result. The package is small (1,331 lines, 271 statements, 0 dependencies) and every gate is green.
What is left is a **short list of sharp edges** and not a redesign: **a manager that is falsy when
it is empty, a manager that `copy.copy` silently aliases, arguments of `EventHandler` that fail late
or with a message that does not name them, a second copy of "is this registered", one condition
without `reset`, and documents, contributor instructions and tests that drifted from their own
rules**. Breaking changes are accepted (the README says the API is unstable before 1.0), and three of
the four code steps below are one, each small; the design itself is at its target and the review
says so instead of inventing work.

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, one behaviour per test).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.13.3,
Apple laptop, scripts kept outside the repository) or **[reading]** (from the code or the
documents). Nothing in `src`, `tests` or `docs` was changed by this review. The code changes were
prototyped in a copy of the package (section 7).

**Baseline on `main`** [verified]: `ruff check`, `ruff format --check` and `ty check` clean; 330
unit and integration tests pass in 1.5 s with 100% line and branch coverage (271 statements, 54
branches); 22 source doctests pass; `PATH=.venv/bin:$PATH .venv/bin/inv test.doctest` exits 0 and
also checks the markdown pages. The items below are what this baseline does not catch.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _event handler_, _event manager_) plus the `Subscription`
that a registration returns and the plain-callable _conditions_. These are the rules. Each design
choice exists to make one of them true **by construction** instead of by discipline. The "Enforced
by" column names the test that enforces the property today (all verified to exist); **gap** marks a
clause with no test, and the finding that closes it. P3, P4, P13 and P16 are stated here **as they
must be after the changes**: today each has a clause that is false (F1, F3, F4, F5).

| #   | Property                 | Statement                                                                                                                                                                                                                                                                                                           | Enforced by                                                                                                                                                                                                          |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | Small surface            | Three concepts and plain callables. Seven exported names and `__version__`. `EventManager` has **8** public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.                                            | `__all__` is reviewed in each PR; no test (trivial structure, `CLAUDE.md`); **the document says 9 (F6)**                                                                                                             |
| P2  | Events are strings       | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                  | `..._add_event_handler_event_must_be_str`, `..._trigger_event_unknown_event_does_not_register_it`, `..._get_subscriptions_does_not_create_event`                                                                     |
| P3  | Validated at the door    | A wrong type or value raises `TypeError` **in the call that receives it**, with a message that names the argument and the value: the event, the handler of `add_event_handler`, the callable, **`handler_args`, `handler_kwargs` (a mapping with `str` keys)** and the condition of `EventHandler`.                 | `..._event_handler_must_be_event_handler`, `..._invalid_event_handler_is_not_registered`, `test_event_handler_incorrect_handler`, `..._incorrect_handler_args`, `..._condition_incorrect_type`; **gap: kwargs (F3)** |
| P4  | Registration identity    | `add_event_handler` returns a new `Subscription` every time; the same handler can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`. **`active` is `True` if and only if the registration is in the manager.**                                      | `test_subscription_remove_*`, `..._duplicate_event_handlers`, `test_subscription_active_*`; **gap: a subscription that was never registered (F4)**                                                                   |
| P5  | Registration order       | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                         | `get_subscriptions_keeps_order`, `test_subscription_remove_middle_keeps_order`, `atrigger_event_mixes_sync_and_async_in_order`                                                                                       |
| P6  | Snapshot dispatch        | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                                                                                            | `..._added_during_dispatch_*`, `..._removed_during_dispatch_*`, `atrigger_event_snapshot`                                                                                                                            |
| P7  | Fail-fast with context   | An exception of a handler propagates **unchanged** (same object, same type); the remaining handlers are skipped. It carries a note with the event and the handler callable, **once per distinct pair**. Building the note never runs the `repr` of user data.                                                       | `..._raises_same_exception_type_and_object`, `..._adds_note`, `..._reused_exception_has_one_note`, `..._note_ignores_repr_of_arguments`, `test_add_error_note_*`                                                     |
| P8  | `once` is at-most-once   | A `once` registration is removed **before** its handler is called, by an atomic claim: it runs at most once whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                                                                                                | `test_once_handler_runs_once_when_snapshots_taken_before_dispatch` (barrier), `..._once_removed_when_condition_false`, `..._once_handler_raises`                                                                     |
| P9  | Synchronous by default   | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop.                                                                                     | `test_event_handler_handle_coroutine_raises`, `..._is_closed`, `test_manager_async.py`                                                                                                                               |
| P10 | Thread-safe registry     | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run **outside** the lock, so a handler can use the manager.                                                                                                                                                      | `tests/integration/test_manager_threads.py`, `..._trigger_event_runs_handler_without_lock`                                                                                                                           |
| P11 | No hidden state          | No global manager, no discovery, no side effect of a read. Zero runtime dependencies. `import minevent` does not import `importlib.metadata`. **A manager cannot be copied or pickled** (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`): it owns a lock and a registry, so create a new one. | `tests/package_checks.py` (`check_no_third_party_import`, `check_lazy_imports`); **gap: copy (F2)**                                                                                                                  |
| P12 | Payload is data          | `trigger_event(event, /, **payload)` passes the payload to every handler as keyword arguments, after `handler_kwargs`. Any key is allowed (`event`, `self`). With `filter_payload=True` only the keys the signature accepts are passed.                                                                             | `..._payload_with_event_and_self_keys`, `test_event_handler_filter_payload_*`, `..._payload_conflicts_with_handler_kwargs`                                                                                           |
| P13 | Conditions are callables | A condition is a `Callable[[], bool]`, called once per trigger and per handler, before the handler. The built-in conditions keep per-instance state **and both have `reset()`**; sharing an instance shares the state. There is **one** way to run a handler once (`once=True`).                                    | `test_event_handler_condition_*`, `test_conditions.py`; **gap: `AfterNCondition.reset` (F5)**                                                                                                                        |
| P14 | Typed                    | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                                                  | `ty` in `ci-type-checking.yaml`                                                                                                                                                                                      |
| P15 | Fast and linear          | A trigger of one handler costs about 0.5 µs, each extra handler about 0.15 µs, a registration plus its removal about 0.9 µs. Registering _k_ handlers and removing them in any order costs O(_k_) in total. Not slower than today.                                                                                  | `tests/benchmarks/` (nightly gate at 50%), including `test_subscription_remove_many_lifo_benchmark`                                                                                                                  |
| P16 | A manager is a service   | `bool(manager)` is always `True`, empty or not, so `manager or default` and `if manager:` mean "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                 | `test_event_manager_len_*`; **gap: truthiness (F1)**                                                                                                                                                                 |

### Not guaranteed, and documented as such

- **Order across threads.** Two threads that trigger the same event run the handlers concurrently,
  in no defined interleaving. A handler that shares state must protect it.
- **State of conditions under threads.** `PeriodicCondition` and `AfterNCondition` update a counter
  without a lock.
- **A handler removed while a trigger is running** still runs in that trigger (P6). After `remove()`
  returns, the next trigger does not run it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A handler that returns a generator** (a `def` with `yield`) does nothing: the generator is
  never iterated. Only awaitables are detected (P9).
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  dict, `Subscription`, manager): `del manager` does not free it until the garbage collector runs,
  while an empty manager is freed at once **[verified]**. Call `reset()` to release the handlers at
  a known point (the guide already says so).

---

## 2. Constraints on the target

1. **Simple and easy to maintain.** Fewer concepts, one way to do each thing. A change that adds
   code must remove a defect or a duplicate; a change that only adds a feature is a decision (D4),
   not a default.
2. **Breaking changes are accepted.** Migration notes go in `CHANGELOG.md`, with the PR number.
3. **No slower than today.** Benchmark gate in section 9: a row more than 10% slower needs a reason.
4. **Documented guarantees are true and tested.** Every property of section 1 names the test that
   enforces it; a property without a test is a finding.
5. **No runtime dependency, heavy imports lazy.** Standard library only. `inspect` stays a
   module-level import by decision of the maintainers (PR #749), so it is not a finding.
6. **Python `>=3.11`.** `BaseException.add_note` and `typing.Self` are used.
7. **The repository follows its own rules.** `CLAUDE.md` and `CONTRIBUTING.md` are checked like code:
   a command that does not exist, or a test that breaks a rule, is a finding.

---

## 3. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Status         |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| F1  | **An empty `EventManager` is falsy.** `__len__` is defined, so `bool(EventManager())` is `False`. The pattern `self.manager = manager or EventManager()` in a class that receives the manager before the handlers are registered (the one the guide shows: create the manager, pass it to `Trainer`, then set up the handlers) silently replaces the caller's manager by a new one: `(m or EventManager()) is m` is `False`. The handlers registered later on `m` never run.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | **[verified]** |
| F2  | **`copy.copy(manager)` aliases the registry.** A shallow copy shares the same `_subscriptions` dict and the same lock: a registration added to the copy shows up in the original (`"e" in m` is `True`). `copy.deepcopy` and `pickle` raise a cryptic `TypeError: cannot pickle '_thread.RLock' object`. Three operations on the same object, one silent bug and two unhelpful errors.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | **[verified]** |
| F3  | **P3 is false for `handler_args` and `handler_kwargs`.** `EventHandler(print, 5)` raises `'int' object is not iterable`; `handler_kwargs=5` raises the same; `handler_kwargs=[1]` raises `cannot convert dictionary update sequence element #0 to a sequence`: none names the argument. `handler_kwargs={1: 2}` is **accepted** and fails at **every** `handle()` with `keywords must be strings`, at trigger time and far from the registration that is wrong. `CLAUDE.md` asks for a message that names the argument and the value, in the function that receives it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | **[verified]** |
| F4  | **"Is this registered" is stored twice.** The registry says it, and `Subscription._active` repeats it; `_remove`, `clear_event` and `reset` must all remember to flip the flag (`reset` walks every subscription to do it). A hand-built `Subscription(manager, "e", handler)` is `active == True` while `remove()` returns `False` and the registry is empty, and stays `True` after `remove()`. The flag has no reader besides the property.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | **[verified]** |
| F5  | **`AfterNCondition` has no `reset`.** `PeriodicCondition` has `reset()` (docstring: "Use `reset` to restart the counter"), and both are stateful and documented as such. The only way to restart an `AfterNCondition` is to build a new one and re-register the handler.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | **[verified]** |
| F6  | **`architecture.md` P1 says `EventManager` has 9 public members; it has 8.** `dir(EventManager)` without underscore: `add_event_handler`, `atrigger_event`, `clear_event`, `events`, `get_subscriptions`, `on`, `reset`, `trigger_event`. The first review's property table was copied without being counted. Nothing checks the number.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | **[verified]** |
| F7  | **`CONTRIBUTING.md` step 4 runs a command that does not exist.** `make unit-test-cov` fails with `No rule to make target`. The file also never mentions `ty` or the invoke tasks (`inv test.unit`, `inv test.doctest`), which are what `CLAUDE.md` and CI use. A new contributor fails at the second step.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | **[verified]** |
| F8  | **The tests break the rules of `CLAUDE.md` in a few places.** An AST audit of 334 test functions: 22 have more than one `assert`/`raises`; 12 are the allowed cases (3 thread tests that assert count and uniqueness; 8 `EventHandler` tests that assert `call_count`, `args` and `kwargs`; 1 on the state of the `Tracer` helper). The other **10 break a rule**: 9 tests combine `pytest.raises` and an `assert` on the note (`..._adds_note`, `..._nested_events_have_one_note_each`, `..._invalid_event_handler_is_not_registered`, ...), and `test_load_runs_skips_old_results_and_keeps_the_file` checks two behaviours. Also: `test_event_manager_trigger_event_retrigger_own_event_has_one_note` has a `pytest.raises(RecursionError)` **without `match`**, and `test_event_manager_trigger_event_reused_exception_has_one_note` has a `for` loop in a unit test. At least five tests of `Subscription` exist twice, once under "subscription conveniences" and once under "Subscription" (`..._active_after_add`/`test_subscription_active_after_add`, `..._active_after_reset`/`test_subscription_inactive_after_reset`, `..._remove_twice`/`..._remove_twice_returns_false`, `..._remove_after_clear_event`/`..._returns_false`, `..._remove_same_handler_instance_twice`/`..._registered_twice_*`) **[reading]**. | **[verified]** |
| F9  | **The documents are longer than the code and say things twice.** `docs/docs` is 1,549 lines for 1,331 lines of source. `architecture.md` (402 lines) states the same ideas three times: the design principles, the "Design Decisions" section (Why strings, Why synchronous, Why an explicit manager) and the "Conclusion". The guide's "Troubleshooting" and "Pitfalls" overlap the FAQ. `review/suggestions.md` (405 lines) describes the code at `976989a`, which still had `coola`, `has_event_handler` and `last_triggered_event`; nearly every item is fixed or obsolete, and it contradicts this document.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | **[reading]**  |

### Measured and kept

- **Debug logging uses the `repr` of the handler.** `logger.debug("Added %s ...", event_handler)`
  formats the handler, arguments included, when a `DEBUG` handler is attached: a 10 MB argument is
  formatted at each add and remove, and a `repr` that raises prints a `--- Logging error ---` block
  (the call itself does not fail) **[verified]**. Naming the handler with `_describe` is not free:
  the argument is evaluated even when the level is off, and `add_event_handler(...).remove()` goes
  from 937 ns to 1,535 ns **[verified]**; a guard adds a branch to two hot paths. Kept (settled in
  the second review); the guide's Debug section says that `DEBUG` logs use the `repr` of the handler.
- **`inspect` is 12.2 ms of the 26.5 ms cumulative import** (`-X importtime`, of which `site` is
  8 ms) **[verified]**. It is used only by `filter_payload`. Kept by decision of the maintainers
  (PR #749); a lazy import is a one-line change if that decision is reopened.
- **`filter_payload` and `handler_args`.** `EventHandler(f, [1], filter_payload=True)` with
  `def f(a, b)` and a payload that has `a` raises `TypeError: f() got multiple values for argument
'a'` **[verified]**. This is the documented conflict rule (a key bound twice is a `TypeError`, with
  or without the filter); the message names the function and the argument. Kept.
- **The note of a lambda is `raised by <lambda>`**, and a condition that raises gets the note of
  its handler. The exception type and the traceback say where it came from. Kept.
- **A handler registered by a running handler** runs at the next trigger, not the current one
  **[verified]** (P6). **A future returned by a synchronous handler** raises the P9 `TypeError`
  (it is awaitable): the message names the handler. Both kept.
- **`once` consumed by a false or a raising condition**, **a cancelled `atrigger_event`**, **`reset()`
  called by a handler**: settled in the earlier reviews, unchanged.

### What already works and must not regress

- Snapshot dispatch with the handlers outside the lock (P6, P10), `RLock` so a handler can use the
  manager, and `once` claimed atomically.
- The registry is a `dict` used as an ordered set: O(1) removal, same order, and the identity hash
  of `Subscription` (no `__eq__`, pinned by `test_subscription_is_hashable_by_identity`).
- `event` and `self` as payload keys (`event` is positional-only), the awaitable check in `handle`
  (a coroutine is closed, so no `RuntimeWarning`), `filter_payload`, `handler_kwargs` copied,
  `str` and `bytes` `handler_args` rejected, array-like `handler_args` accepted (`() if handler_args
is None else tuple(handler_args)`, not `handler_args or ()`).
- One note per distinct pair; the `on` options; the non-goals (event objects, priorities, weak
  references, collecting errors).
- The test suite has no local import and no sleep in `tests/unit`.

---

## 4. Architecture

```text
EventManager ──registry──▶ {event: {Subscription: None, ...}}      insertion order = run order
     │                          event, event_handler, once
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
every property. The registry is the **only** record of what is registered (F4): a `Subscription`
holds no state of its own.

| Module          | Contains                                                     | Lines |
| --------------- | ------------------------------------------------------------ | ----: |
| `conditions.py` | `Condition` protocol, `PeriodicCondition`, `AfterNCondition` |   204 |
| `handlers.py`   | `BaseEventHandler`, `EventHandler`                           |   391 |
| `manager.py`    | `EventManager`, `Subscription`                               |   681 |

### 4.1 A manager is truthy (F1, P16)

```python
class EventManager:
    def __bool__(self) -> bool:
        return True
```

`__len__` stays (number of registrations). Without this, "is there a manager" and "does the manager
have a handler" are the same expression. Python's rule "an empty container is falsy" fits a
collection; a manager is a service. The alternative, dropping `__len__`, removes a documented and
tested method for a rare idiom (D1).

### 4.2 A manager is not copyable (F2, P11)

```python
def __reduce__(self) -> NoReturn:
    msg = f"{type(self).__qualname__} cannot be copied or pickled: create a new one"
    raise TypeError(msg)
```

`copy.copy`, `copy.deepcopy` and `pickle.dumps` all go through `__reduce_ex__`, so one override gives
the same clear error to the three **[verified]** on a subclass. The silent alias of `copy.copy`
disappears, and the two cryptic errors say what to do.

### 4.3 `active` reads the registry (F4, P4)

```python
# Subscription
@property
def active(self) -> bool:
    return self._manager._is_registered(self)  # no _active attribute


# EventManager
def _is_registered(self, subscription: Subscription) -> bool:
    with self._lock:
        return subscription in self._subscriptions.get(subscription.event, ())


# _remove: delete the line `subscription._active = False`
# clear_event: `self._subscriptions.pop(event, None)`, no loop
# reset: `self._subscriptions.clear()`, no loop
```

One source of truth. A subscription that was never registered is inactive (`False`, as `remove()`
says). `active` costs 170 ns instead of 29 ns (a lock and a lookup instead of an attribute); it is
not on the trigger path. `reset` and `clear_event` lose their loops: 5.9 ms instead of 6.8 ms for
100,000 registrations (the time is the deallocation, not the flag).

### 4.4 Arguments of `EventHandler` are validated where they arrive (F3, P3)

```python
try:
    args = () if handler_args is None else tuple(handler_args)
except TypeError:
    msg = f"handler_args must be a sequence of arguments, but got {handler_args!r}"
    raise TypeError(msg) from None
try:
    kwargs = {} if handler_kwargs is None else dict(handler_kwargs)
except (TypeError, ValueError):
    msg = f"handler_kwargs must be a mapping, but got {handler_kwargs!r}"
    raise TypeError(msg) from None
if not all(isinstance(key, str) for key in kwargs):
    msg = f"the keys of handler_kwargs must be str, but got {list(kwargs)!r}"
    raise TypeError(msg)
```

The `str`/`bytes` check for `handler_args` stays. `filter_payload` is a flag: it is not validated
(the type checker covers it, and a validator for a flag is a validator that is one `isinstance`,
which `CLAUDE.md` forbids). Result of the prototype: `handler_args=5` → `handler_args must be a
sequence of arguments, but got 5`; `handler_kwargs={1: 2}` → `the keys of handler_kwargs must be
str, but got [1]`, at construction.

### 4.5 `AfterNCondition.reset` (F5, P13)

```python
def reset(self) -> None:
    self._step = 0
```

Same docstring and example as `PeriodicCondition.reset`. Both conditions are then restartable and
the "stateful condition" paragraph of the guide is true for both.

---

## 5. Public API after the change

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

| Signature                                                         | Change                                                                       |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `bool(EventManager())`                                            | `True` instead of `False` for an empty manager (F1)                          |
| `copy.copy`, `copy.deepcopy`, `pickle.dumps` of an `EventManager` | one clear `TypeError` instead of a silent alias and a cryptic error (F2)     |
| `EventHandler(..., handler_args, handler_kwargs)`                 | `TypeError` that names the argument; non-`str` keys rejected at construction |
| `Subscription.active`                                             | `False` for a subscription that was never registered (F4)                    |
| `AfterNCondition.reset() -> None`                                 | new method (F5)                                                              |
| every other signature, every exported name                        | unchanged                                                                    |

### Migration

| Code                                                                   | After                                 |
| ---------------------------------------------------------------------- | ------------------------------------- |
| `if not manager:` to test that the manager has no handler              | `if len(manager) == 0:`               |
| `copy.copy(manager)` to share a manager                                | pass the same object                  |
| `EventHandler(f, handler_kwargs={1: 2})`, failing at the first trigger | fails at construction, with a message |
| Code that reads `Subscription.active` of a hand-built `Subscription`   | `False`                               |

Nothing else breaks. There is no release between the third review and this one, so the changelog
entries stay under _Unreleased_.

---

## 6. Dependents

| Place                                | Change                                                                                                                                                                                                                        |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/docs/architecture.md`          | Replace the properties table by the one of section 1 (same ids, without the "Enforced by" column): 8 members, P3, P4, P11, P13, P16. Delete "Design Decisions" and "Conclusion" (about 70 lines, F9).                         |
| `docs/docs/guide.md`, `faq.md`       | Add the sentences "a manager is always truthy", "a manager cannot be copied", "`reset()` of both stateful conditions"; Debug section: `DEBUG` logs use the `repr` of the handler. Merge "Troubleshooting" into the FAQ links. |
| `CONTRIBUTING.md`                    | Replace `make unit-test-cov` by `inv test.unit --cov`; add `inv test.doctest`, `ty check` and `ruff` next to `pre-commit run --all-files` (F7).                                                                               |
| `review/suggestions.md`              | **Delete** (F9). It describes a state two rewrites old; this file replaces it.                                                                                                                                                |
| `src/minevent/manager.py` docstrings | `EventManager` (truthy, not copyable), `Subscription.active` (registry), `_is_registered`.                                                                                                                                    |
| `src/minevent/handlers.py` docstring | `EventHandler` `Raises:` (`handler_args`, `handler_kwargs` and its keys).                                                                                                                                                     |
| `src/minevent/conditions.py`         | `AfterNCondition.reset`, and the class docstring ("use `reset` to restart").                                                                                                                                                  |
| `CHANGELOG.md`                       | Under _Unreleased_: truthiness, copy, `EventHandler` validation, `active`, `AfterNCondition.reset`. PR numbers.                                                                                                               |
| `tests/`                             | Section 9.                                                                                                                                                                                                                    |

---

## 7. Evidence

All on `main` at `df13132`, Python 3.13.3, Apple laptop, minimum of 5 to 7 `timeit` repeats, scripts
in the session scratchpad (not committed).

**Behaviour**

| Probe                                                         | `main`                                                  | Target (prototype)                               |
| ------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| F1: `bool(EventManager())`                                    | `False`                                                 | `True`                                           |
| F1: `(m or EventManager()) is m`                              | `False`                                                 | `True`                                           |
| F2: `copy.copy(m)`, then add to the copy, `"e" in m`          | `True` (shared registry, same lock)                     | `TypeError: ... cannot be copied or pickled`     |
| F2: `copy.deepcopy(EventManager())`                           | `TypeError: cannot pickle '_thread.RLock' object`       | same clear `TypeError`                           |
| F3: `EventHandler(print, 5)`                                  | `'int' object is not iterable`                          | `handler_args must be a sequence ..., but got 5` |
| F3: `EventHandler(print, handler_kwargs=[1])`                 | `cannot convert dictionary update sequence element #0`  | `handler_kwargs must be a mapping, but got [1]`  |
| F3: `EventHandler(print, handler_kwargs={1: 2})`              | accepted; `.handle()` raises `keywords must be strings` | `TypeError` at construction                      |
| F4: `Subscription(m, "e", h)`: `active`, `remove()`, `active` | `True`, `False`, `True`                                 | `False`, `False`, `False`                        |
| F5: `AfterNCondition(2).reset`                                | `AttributeError`                                        | restarts the counter                             |
| F6: public members of `EventManager`                          | 8 (the document says 9)                                 | document says 8                                  |
| F7: `make unit-test-cov`                                      | `No rule to make target`                                | `inv test.unit --cov`                            |
| debug log with a raising `repr` argument, handler attached    | `--- Logging error ---` block, add succeeds             | unchanged, documented                            |
| manager with one registration, `del manager`, `gc` disabled   | not freed (cycle); freed after `gc.collect()`           | unchanged, documented                            |

**Speed and size** (prototype of 4.1 to 4.5 in a copy of the package; only `src` changed)

| Benchmark                                       |   `main` | Prototype | Note                                          |
| ----------------------------------------------- | -------: | --------: | --------------------------------------------- |
| `trigger_event`, no handler                     |   289 ns |   not run | unchanged by the change                       |
| `trigger_event`, 1 handler                      |   484 ns |    486 ns | inside the run-to-run spread                  |
| `trigger_event`, 10 handlers                    | 1,878 ns |   not run | 0.15 µs per handler: the number for the docs  |
| `add_event_handler` then `remove()`             |   937 ns |    934 ns | no change                                     |
| `Subscription.active`                           |    29 ns |    170 ns | a lock and a lookup; not on a hot path        |
| `reset()` of 100,000 registrations              |   6.8 ms |    5.9 ms | the loop of flags is gone                     |
| `add ... remove()` with `_describe` in the log  |   937 ns |  1,535 ns | **rejected** (section 3, "Measured and kept") |
| `import minevent` (`-X importtime`, cumulative) |  26.5 ms |   26.5 ms | `inspect` is 12.2 ms of it; kept by decision  |
| `src` lines                                     |    1,331 |    ~1,345 | before the docstrings the rules require       |

The **330 existing tests pass against the prototype with no edit**, which shows that nothing
documented depended on the old behaviour. The new tests of section 9 are not in the prototype.

---

## 8. Changes to reach the target state

One branch and one PR per row, branched from `main` (the rows are independent; stack them in this
order if they are in flight together). Every PR updates the changelog with its number, has its
tests, and keeps `ruff`, `ty` and 100% coverage.

| Step | Change                                                                                                                                                                                                   | Breaking                                |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| 1    | **Documents tell the truth** (F6, F7, F9; docstrings only): properties table of section 1, `CONTRIBUTING.md` commands, `architecture.md` trimmed, guide Debug sentence, `review/suggestions.md` deleted. | no                                      |
| 2    | **A manager is truthy and not copyable** (F1, F2): sections 4.1 and 4.2. Regression tests first, and check they fail on `main` with `git stash push src`.                                                | `if not manager:`; `copy.copy(manager)` |
| 3    | **`active` reads the registry** (F4): section 4.3. The property tests of `Subscription` stay as they are; add the never-registered one.                                                                  | `active` of a hand-built subscription   |
| 4    | **Arguments of `EventHandler` are validated** (F3): section 4.4, with the messages of the evidence table.                                                                                                | `handler_kwargs` with non-`str` keys    |
| 5    | **`AfterNCondition.reset`** (F5): section 4.5. Skip this step if D3 is declined.                                                                                                                         | no                                      |
| 6    | **Test hygiene** (F8; tests only, no `src` change): section 9.                                                                                                                                           | no                                      |

All six steps are safe to merge alone and in any order. Steps 2 and 3 both edit `manager.py` (the
class docstring of `EventManager`); on a conflict keep both sentences.

---

## 9. Tests and gates

New or changed tests (the existing 330 stay). Each is one behaviour, with `match` on every
`pytest.raises`, and each regression test is checked to fail on `main`.

- **Truthiness and copy (P11, P16, F1, F2).** `bool(EventManager())` is `True`; `bool` of a manager
  with a registration is `True`; `copy.copy`, `copy.deepcopy` and `pickle.dumps` each raise
  `TypeError` with `match=r"cannot be copied or pickled"` (parametrize over the three).
- **`active` (P4, F4).** A hand-built `Subscription(manager, "e", handler).active` is `False`;
  `active` is `False` after `clear_event`, `reset`, `remove`, and a consumed `once` (the existing
  tests); `_is_registered` is tested on its own: registered, removed, never registered, another event
  (`CLAUDE.md`: private functions have tests).
- **`EventHandler` validation (P3, F3).** `handler_args=5`, `handler_kwargs=5`, `handler_kwargs=[1]`
  and `handler_kwargs={1: 2}` each raise `TypeError` with a `match` that names the argument
  (parametrize); valid cases still work: `handler_kwargs` as a `dict` and as any `Mapping`, `handler_args` as a
  tuple, a list, an array-like (the existing tests).
- **`AfterNCondition.reset` (P13, F5).** After `reset`, the first `n` calls are `False` again; a
  fresh condition and a reset condition give the same sequence (`[False, False, True]` against a
  literal).
- **Test hygiene (F8).** Replace the nine `pytest.raises` + `assert` note tests by one helper in
  `tests/unit/utils.py` that returns the raised exception, so each test has one assert:

  ```python
  def raised(func: Callable[..., object], *args: object, **kwargs: object) -> BaseException:
      """Return the exception raised by a call, and fail if it does not raise."""
      try:
          func(*args, **kwargs)
      except BaseException as exc:  # noqa: BLE001
          return exc
      pytest.fail("did not raise")
  ```

  `assert raised(manager.trigger_event, "e").__notes__ == [...]`. Add `match` to the
  `RecursionError` test, parametrize the loop of `..._reused_exception_has_one_note`, split
  `test_load_runs_skips_old_results_and_keeps_the_file` in two, and delete the five duplicated
  `Subscription` tests (keep the ones under "Subscription").

- **Integration** (`tests/integration/`): the thread tests pass with no edit. Add none: the changes
  do not touch concurrency (the lock is the same; `_is_registered` takes it).
- **Benchmark gate.** `inv test.benchmark` before and after steps 2 to 4; a trigger row more than
  10% slower is explained in the PR. Add one row: `Subscription.active` (so the 29 → 170 ns change is
  seen, not guessed). The nightly workflow fails at 50% on a median.
- **Doctests.** `PATH=.venv/bin:$PATH .venv/bin/inv test.doctest` after steps 1, 2, 4 and 5: source
  and the markdown files. New examples: `bool(EventManager())`, the `EventHandler` `Raises:`,
  `AfterNCondition.reset`.
- **Coverage.** 100% line and branch on `src/minevent`, no `# pragma: no cover`.
- **Lint and types.** `ruff check`, `ruff format --check`, `ty check` on `src` and `tests`.

---

## 10. Decisions for the maintainers

Decisions of the earlier reviews (snapshot dispatch, `once` consumed on a false condition or a
raising handler, sequential async, no lock in conditions, `handler_args`/`handler_kwargs` kept,
one-line `repr`s, lazy `__version__`, `get_subscriptions`, bare function rejected by
`add_event_handler`, note without `repr`, `inspect` imported at module level, the `Tracer` helper,
`logger.debug` kept, `dev/benchmark_trend.py` kept, `dict` as an ordered set, dedupe of notes, `on`
forwards `condition` and `filter_payload`, no weak reference to break the cycle, the dispatch loops
of `trigger_event` and `atrigger_event` not shared, a condition without the payload) are settled and
not reopened.

| #   | Question                                                                                  | Recommendation                                                                                                                                                                                                                                                                                                                                   |
| --- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Truthiness: `__bool__` returning `True`, drop `__len__`, or document the empty-is-falsy?  | **`__bool__`.** Three lines, no removed API, and the idiom `manager or default` becomes safe. Alternative: drop `__len__` (a documented, tested method; `len` is how the tests count registrations) or only document it, which leaves a bug that passes review because the code reads as correct.                                                |
| D2  | `copy`/`pickle` of a manager: raise a clear error, or support copying?                    | **Raise.** A copy has two defensible meanings (share the registry or clone the registrations), the handlers are user objects that may not be copyable, and the lock cannot be pickled. Refusing is one method and no policy. Alternative: `__copy__` that returns a new empty manager is a third meaning and would be a surprise.                |
| D3  | Add `AfterNCondition.reset`, or remove `PeriodicCondition.reset`?                         | **Add.** Two stateful conditions with the same lifecycle should have the same methods; `reset` is two lines. Alternative: remove `reset` from both (breaking, and a user who calls it every epoch loses it) and say "build a new condition".                                                                                                     |
| D4  | Validate `handler_kwargs` keys at construction?                                           | **Yes, and the types of `handler_args` and `handler_kwargs`.** P3 says arguments are validated at the door, and a non-`str` key is the one error that today appears at trigger time. A flag (`filter_payload`, `once`) is not validated: that is a type-checker job. Alternative: validate nothing more and delete the "arguments" clause of P3. |
| D5  | Delete `review/suggestions.md`?                                                           | **Yes.** It is two rewrites old and wrong in its premises (`coola`, `has_event_handler`). `git log` keeps it. Alternative: rewrite it as a backlog; then it must be kept true, which this file already does.                                                                                                                                     |
| D6  | Add a `raised` test helper, or keep `pytest.raises` + `assert` where the note is checked? | **Helper.** The rule of `CLAUDE.md` is one `assert` or one `pytest.raises`; the helper makes the nine tests comply without a new rule, and it is six lines. Alternative: amend `CLAUDE.md` to allow `raises` followed by one `assert` on `exc_info` (simpler, but a rule change for the whole repository).                                       |

---

## 11. Not covered

- **Priorities, wildcards, hierarchical events, event objects.** Non-goals of the architecture page.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). Worth a separate design
  if users ask; it does not change the runtime.
- **Weak references / auto-unsubscribe, collecting errors (`ExceptionGroup`), cross-process or
  persistent events, offloading blocking handlers to a thread.** Non-goals, unchanged.
- **Free-threaded safety of conditions.** Documented limit.
- **Handlers as plain callables** (drop `EventHandler`, or let `add_event_handler` wrap a function).
  It would remove a concept the documents define; settled earlier, and `on` closes most of the
  verbosity.
- **Detecting a handler that returns a generator** (silently dropped, like a coroutine was before
  P9). It is a rarer mistake, `inspect.isgenerator` is one more check on the hot path, and the
  library does not run user generators. Documented in section 1.
- **The `mkdocs` build.** The `docs` dependency group is not installed here, so the generated
  reference (`refs/index.md` documents `minevent`, `refs/manager.md` documents `minevent.manager`,
  so `EventManager` may appear twice) was not rendered. Check it with `mkdocs build --strict` when
  step 1 is reviewed.
- **Repository tooling.** 26 workflows, the shared `.make/` directory and two task runners
  (`invoke` and `make`) are large for a 1,300-line package. They are shared with other projects, so
  they are outside this review (F7 only fixes the instruction that points at them).
- **`tests/unit/test_utils.py`** tests a test helper (`tests/unit/utils.py`), not a module of `src`,
  so it does not mirror the source tree. The maintainers kept the helper; not reopened.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate, the gate is the behaviour of sections 1
and 9, not the size.

| Module                                       | Lines today | Expected after | Why                                                                          |
| -------------------------------------------- | ----------: | -------------: | ---------------------------------------------------------------------------- |
| `conditions.py`                              |         204 |           ~215 | `AfterNCondition.reset` with its docstring (+11)                             |
| `handlers.py`                                |         391 |           ~410 | validation of `handler_args` / `handler_kwargs` and `Raises:` (+19)          |
| `manager.py`                                 |         681 |           ~700 | `__bool__`, `__reduce__`, `_is_registered` with docstring (+22), flags (-3)  |
| `__init__.py`                                |          55 |             55 | unchanged                                                                    |
| **`src`**                                    |   **1,331** |     **~1,380** |                                                                              |
| `src` statements                             |         271 |           ~285 | the three validation branches, `__bool__`, `__reduce__`, `reset`             |
| `tests/` (unit, integration, package checks) |       2,975 |         ~3,000 | new tests (+80), five duplicates and the note boilerplate out (-55)          |
| `tests/benchmarks/`                          |         428 |           ~440 | one row                                                                      |
| `docs/docs`                                  |       1,549 |         ~1,490 | properties table in, "Design Decisions" and "Conclusion" out                 |
| `review/`                                    |         886 |           ~490 | `suggestions.md` (405) out, this file (about 490) replaces the old one (481) |
| Runtime dependencies                         |           0 |              0 |                                                                              |
| `import minevent`                            |     26.5 ms |       ~26.5 ms | unchanged                                                                    |
