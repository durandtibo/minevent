# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent` and proposes the smallest design that has all of
them. The package is small, and the proposal is to make it smaller: one registration record
(`Subscription`) that is both the identity and the state of a registration, plain callables for
conditions, no equality protocol, no dependency. Breaking changes are accepted (the README says the
API is unstable before 1.0), and most of the removed names have never been released (they are in
`Unreleased`), so removing them is free.

It follows `review/suggestions.md`, whose items 1 to 3 are merged on `main`. This review starts from
the code at `951a999` (412 unit and integration tests, 100% line and branch coverage, ruff and ty
clean) and looks at what remains. The principles come from `docs/docs/architecture.md` (simplicity
first, synchronous by design, explicit over implicit, composition, zero magic, the non-goals).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`) or
**[reading]** (from the code or the documents). The prototype of section 6 is a throwaway; it is not
committed.

## Constraints

1. **Simple and easy to maintain.** Fewer concepts, fewer classes, one way to do each thing.
2. **Breaking changes are accepted.** Migration notes go in `CHANGELOG.md`, with the PR number.
3. **No slower than today.** Benchmark gate in section 8.
4. **Documented guarantees are true.** Every property of section 1 has a test, and the
   documentation says nothing the code does not do.
5. **Optional and heavy imports stay lazy.** `__version__` stays lazy (D12).
6. **Python `>=3.11`.** `BaseException.add_note` and `typing.Self` are used.

---

## 1. Properties of the sub-package

| #   | Property                 | Statement                                                                                                                                                                                                                                   | Enforced by                                               |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| P1  | Small surface            | Three concepts: _event_ (a `str`), _event handler_, _event manager_. Plus the `Subscription` returned by a registration and plain-callable _conditions_. Nothing else is public.                                                            | `__all__` reviewed in each PR; docs index lists the names |
| P2  | Events are strings       | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is a valid name. Reading the manager never creates an event.                                                                                   | unit tests (exist)                                        |
| P3  | Registration identity    | `add_event_handler` returns a new `Subscription` every time. The same handler can be registered several times. `Subscription.remove()` removes that registration only, once, and returns `True` the first time, then `False`.               | regression test for F1 (new)                              |
| P4  | Registration order       | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                 | unit tests (exist)                                        |
| P5  | Snapshot dispatch        | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                    | unit tests (exist)                                        |
| P6  | Fail-fast with context   | An exception of a handler propagates unchanged to the caller of `trigger_event`; the remaining handlers are skipped. The exception carries a note with the event name and the handler.                                                      | unit test (new)                                           |
| P7  | `once` is at-most-once   | A `once` registration is removed **before** its handler is called, by an atomic claim: it runs at most once, whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                       | barrier test (new, deterministic)                         |
| P8  | Synchronous by default   | `trigger_event` never awaits. A handler that returns an awaitable is an error (`TypeError`). `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop.                                  | unit tests (exist)                                        |
| P9  | Thread-safe registry     | The registry is protected by a reentrant lock. Handlers, conditions and `repr` of user objects run **outside** the lock, so a handler can use the manager.                                                                                  | threads integration tests (exist, extended)               |
| P10 | No hidden state          | No global manager, no discovery, no registration side effect of a read. Zero runtime dependencies.                                                                                                                                          | `pyproject.toml`; `package_checks.py` imports the wheel   |
| P11 | Payload is data          | `trigger_event(event, /, **payload)`: the payload is passed to every handler as keyword arguments, after `handler_kwargs`. Any key is allowed (`event`, `self`). With `filter_payload=True` only the keys the signature accepts are passed. | unit tests (exist)                                        |
| P12 | Conditions are callables | A condition is a `Callable[[], bool]`, called once per trigger and per handler, before the handler. The built-in stateful conditions keep per-instance state; sharing an instance shares the state.                                         | unit tests (exist, simplified)                            |
| P13 | Typed                    | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                          | `ty` in CI (exists)                                       |
| P14 | Fast                     | The trigger of one handler costs about 0.6 µs; adding a registration about 0.6 µs. Not slower than today.                                                                                                                                   | benchmark gate (new, section 8)                           |

### Not guaranteed, and documented as such

- **Order across threads.** Two threads that trigger the same event run the handlers concurrently,
  in no defined interleaving. A handler that shares state must protect it.
- **State of conditions under threads.** `PeriodicCondition`, `AfterNCondition` and `OnceCondition`
  update a counter without a lock (D8).
- **A handler removed while a trigger is running** still runs in that trigger (P5), as in a
  snapshot. After `remove()` returns, the next trigger does not run it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`. Guard it
  with a condition or a flag.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.

---

## 2. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Status     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| F1  | **P3 is false.** The docstring says a `Subscription` "removes exactly the registration that created it", but removal is by handler identity. With `h = EventHandler(print)` registered twice, `s1.remove()` returns `True` and `s1.remove()` again returns `True` and removes the registration of `s2`; `s2.active` is then `False`. Same for two `once` registrations of one handler.                                                                                                                                                                                                                               | [verified] |
| F2  | **The `once` wrapper leaks into the registry.** `_OnceEventHandler` is stored instead of the user handler, so `_unwrap` is needed in `get_event_handlers`, `has_event_handler` and `remove_event_handler`; its `equal` is asymmetric (`wrapper == handler` is `True`, `handler == wrapper` is `False`); `subscription` is a public mutable attribute set after construction; `Subscription` needs two callbacks (`remove_func`, `is_active_func`) and `active` is an O(n) scan.                                                                                                                                      | [verified] |
| F3  | **Equality-based lookup is the weakest part of the API.** `equal` / `__eq__` on handlers and conditions (two abstract `equal`, two `# noqa: PLW1641`, unhashable by design), `has_event_handler` and `remove_event_handler`-by-handler cannot find lambdas, closures or bound methods of another instance. `Subscription` already covers every use. The quickstart teaches it in 10 places and the troubleshooting page in 7.                                                                                                                                                                                        | [verified] |
| F4  | **`coola` is the only dependency and 88% of the import time.** `import minevent` takes 35.5 ms, of which `coola.equality` (which imports `coola`) takes 31 ms; the prototype without it imports in 10 ms (mostly `inspect` and `typing`). It is used for `objects_are_equal` and three `str_*` formatters. It drives five workflows, `dev/generate_versions.py`, `dev/config/package_versions.json` and the README version table.                                                                                                                                                                                    | [verified] |
| F5  | **Conditions are 30% of `src` for what is a `Callable[[], bool]`.** `BaseCondition` (two abstract methods), `CallableCondition`, `as_condition`, `AlwaysCondition` (`condition=None` already means always), `NotCondition`, `AndCondition`, `OrCondition` (with a private base class, and a "no short-circuit" trade-off to document). 590 lines of 2,002. All of them are in `Unreleased`.                                                                                                                                                                                                                          | [reading]  |
| F6  | **`last_triggered_event` has no use.** It is informational, racy under threads (documented), read by nothing in the library, written under the lock on every trigger, shown in `repr` and cleared by `reset`. It appears 17 times in the quickstart.                                                                                                                                                                                                                                                                                                                                                                 | [reading]  |
| F7  | **`repr` is more complex than the feature.** Multi-line `repr` built with three `coola` formatters; `EventManager.__repr__` copies the registry under the lock so that user `repr` runs outside it (review 1.7), and `_format_event_handlers` exists only for that.                                                                                                                                                                                                                                                                                                                                                  | [reading]  |
| F8  | **`EventHandler.handle` and `ahandle` repeat the same four lines** (condition check, payload selection, call), one awaiting and one rejecting the awaitable.                                                                                                                                                                                                                                                                                                                                                                                                                                                         | [reading]  |
| F9  | **A failing handler does not say which one.** With five handlers on `batch_end`, the traceback shows the handler frame and `EventManager.trigger_event`, not the event name or the registration. `add_note` (3.11) adds it without changing the exception type.                                                                                                                                                                                                                                                                                                                                                      | [verified] |
| F10 | **Several documented properties are false.** `architecture.md` says "No reflection" (`filter_payload` uses `inspect.signature`, the awaitable check uses `inspect`), "No threading complexity" and "Synchronous only" (there is a lock and `atrigger_event`), "Conditional handlers combine handlers and conditions" (there is no such class), and shows `_event_handlers["event"].append(...)`. `architecture.md:244` and `faq.md:167` define `def handle(self) -> None`, which raises `TypeError` as soon as a payload is given. The "Custom Event Manager" sketch has no payload, no `atrigger_event`, no `once`. | [verified] |
| F11 | **The guide pages do not know the API.** `best_practices.md` and `faq.md` never mention `Subscription`, `once=True`, `missing_ok`, `filter_payload` or `atrigger_event`; the README "Features" list has no payload, `once`, subscription, async or thread safety and says "Only depends on `coola`". `faq.md`, `troubleshooting.md` and `best_practices.md` are 1,123 lines for three classes and repeat each other.                                                                                                                                                                                                 | [verified] |
| F12 | **Only the source docstrings are executed.** `ci-doctest.yaml` runs `inv test.doctest` on `src`. The 33 `pycon` blocks of `quickstart.md` and the ones of `README.md` and `index.md` are not run, so the drift of F10 and F11 is not caught.                                                                                                                                                                                                                                                                                                                                                                         | [reading]  |
| F13 | **Packaging claims what is not true.** Empty `[project.optional-dependencies]` with the `autoextras` hook and `lib-get-package-extras.yaml` (an empty `all` extra); `min` CI job identical to `all` (`--no-optional-deps` with none); classifiers "4 - Beta" against the README warning, and Linux and macOS only for pure Python; `--color yes` in `addopts`; no `concurrency` group on `ci.yaml`; no tag against version check in `release-pypi.yaml`.                                                                                                                                                             | [reading]  |
| F14 | **The tests are 7.4 lines per statement.** 3,251 lines of tests for 438 statements. `tests/unit/utils.py` (`Tracer`, 67 lines) re-implements `unittest.mock.Mock(wraps=...)` and has its own `test_utils.py` (86 lines). `CLAUDE.md` tells contributors to use `coola.utils`, `coola.validation`, `LazySingleton` and `coola.testing.marks`, which a package without `coola` does not have.                                                                                                                                                                                                                          | [reading]  |
| F15 | **Stateful conditions are not thread-safe** and CI runs free-threaded builds (`ci-test.yaml`). On the GIL build four threads on a `PeriodicCondition(2)` counted exactly 200,000 `True` in 400,000 calls; the guarantee is not documented as a limit of the free-threaded build.                                                                                                                                                                                                                                                                                                                                     | [verified] |

### What already works and must not regress

- Snapshot dispatch with the handlers outside the lock (P5, P9), and `RLock` so a handler can use
  the manager.
- `once` is claimed atomically (review 1.1, 1.2): 0 failures in 200 rounds of 8 threads.
- `event` and `self` as payload keys (positional-only parameters), the awaitable check in `handle`,
  `filter_payload`, `handler_kwargs` copied, `str` `handler_args` rejected.
- `TypeError` for a non-`str` event, `ValueError` plus `missing_ok` for removal (the removal API is
  reduced in D1, but the error contract of what remains is the same).
- Fail-fast and the documented non-goals (event objects, priorities, weak references, collecting
  errors).
- 100% line and branch coverage and a `filterwarnings = error` test suite.

---

## 3. Architecture

```text
EventManager ──registry──▶ {event: [Subscription, ...]}      (insertion order = run order)
     │                          │  event, event_handler, once, active
     │ trigger_event(event, /, **payload)
     ▼
for sub in snapshot(event):                  # under the lock, a tuple copy
    if sub.once and not manager._remove(sub):  # atomic claim, P7
        continue
    sub.event_handler.handle(**payload)       # outside the lock
         │
         ▼
EventHandler.handle ──▶ condition() ──▶ filter payload ──▶ handler(*args, **kwargs, **payload)
```

One record, `Subscription`, is the registry entry, the identity returned to the user, and the unit of
removal. There is no wrapper handler and no second list.

### 3.1 `Subscription`

```python
class Subscription:
    __slots__ = ("_manager", "_event", "_event_handler", "_once", "_active")

    event: str  # read-only properties
    event_handler: BaseEventHandler
    once: bool
    active: bool

    def remove(self) -> bool:
        """Return True the first time, False after (also after clear_event or reset)."""
        return self._manager._remove(self)

    def __enter__(self) -> Self: ...
    def __exit__(self, *exc) -> None: ...  # remove()
```

- `_active` is set to `False` under the manager lock by `_remove`, `clear_event` and `reset`.
  `active` reads it: no scan, no callback. This is the fix of F1: a second `remove()` sees
  `_active == False` and returns `False`, whatever the handler is.
- Equality and hash are the default (identity). `list.remove(sub)` therefore removes that record.
- The constructor is not part of the public API. The manager builds it; the class docstring says so.
  It takes the manager instead of two callbacks, which removes `remove_func`, `is_active_func`
  and their tests.

### 3.2 Event handlers

```python
class BaseEventHandler(ABC):
    @abstractmethod
    def handle(self, /, **payload: object) -> None: ...

    async def ahandle(self, /, **payload: object) -> None:
        self.handle(**payload)  # default: works for synchronous handlers
```

- No `equal`, no `__eq__`. Handlers are hashable by identity again, so they can go in a `set` or be
  `dict` keys (the long unhashability paragraph of the docstring is deleted).
- `EventHandler(handler, handler_args=None, handler_kwargs=None, *, condition=None, filter_payload=False)`
  keeps its signature (D6). `condition` is any `Callable[[], bool]`; it is no longer wrapped.
- One private method does the shared work, so `handle` and `ahandle` differ only in what they do
  with an awaitable (F8):

```python
def _call(self, payload: dict[str, object]) -> object:
    """Return the result of the handler, or None if the condition is false."""
    if self._condition is not None and not self._condition():
        return None
    if self._payload_keys is not None:
        payload = {k: v for k, v in payload.items() if k in self._payload_keys}
    return self._handler(*self._handler_args, **self._handler_kwargs, **payload)
```

- `handle` raises `TypeError` for an awaitable result (after closing a coroutine); `ahandle`
  awaits it.
- If `handler_kwargs` and the payload share a key, Python raises its own `TypeError` ("multiple
  values for keyword argument"). That is documented in the class docstring and is not special-cased.
- `repr` is one line: `EventHandler(handler=<function f at 0x...>, args=(), kwargs={}, condition=None)`.
  Fields that equal their default are shown anyway; no formatter is needed.

### 3.3 Conditions

```python
class Condition(Protocol):
    def __call__(self) -> bool: ...
```

| Name                | Role                                                                                                                                                        | Today                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `Condition`         | Protocol: any `Callable[[], bool]` (a lambda, a method, a built-in below).                                                                                  | `BaseCondition` ABC with `evaluate` and `equal` |
| `PeriodicCondition` | `True` on the first call and then every `freq` calls (`skip_first`, `reset()`).                                                                             | kept, `evaluate` becomes `__call__`             |
| `AfterNCondition`   | `False` for the first `n` calls.                                                                                                                            | kept, `evaluate` becomes `__call__`             |
| `OnceCondition`     | `True` on the first call only (the handler stays registered; `once=True` unregisters it).                                                                   | kept, `evaluate` becomes `__call__`             |
| removed             | `AlwaysCondition` (use `condition=None`), `CallableCondition` and `as_condition` (a callable is a condition), `NotCondition`, `AndCondition`, `OrCondition` |                                                 |

- Combining conditions is a lambda, and the user chooses the evaluation rule that the library
  imposed today (no short-circuit, with a trade-off to explain). Both forms are documented:

```python
EventHandler(save, condition=lambda: periodic() and has_improved())  # short-circuit
EventHandler(save, condition=lambda: all([periodic(), has_improved()]))  # both advance
```

- Stateful conditions are documented as per-instance state; the docs show a factory
  (`lambda: PeriodicCondition(5)`) for a condition used by several handlers.
- Validation stays as today (`TypeError` for a non-`int` or `bool`, `ValueError` below the bound).
  `EventHandler` raises `TypeError` for a non-callable `condition`.

### 3.4 `EventManager`

State: `_subs: dict[str, list[Subscription]]` and an `RLock`. Nothing else.

```python
def add_event_handler(self, event, event_handler, *, once=False) -> Subscription:
    _check_event(event)
    sub = Subscription(self, event, event_handler, once)
    with self._lock:
        self._subs.setdefault(event, []).append(sub)
    return sub


def _remove(self, sub) -> bool:
    with self._lock:
        if not sub._active:
            return False
        sub._active = False
        subs = self._subs[sub._event]
        subs.remove(sub)
        if not subs:
            del self._subs[sub._event]
        return True


def trigger_event(self, event, /, **payload) -> None:
    for sub in self._snapshot(event):  # checks the type, takes a tuple under the lock
        if sub._once and not self._remove(sub):
            continue
        try:
            sub._event_handler.handle(**payload)
        except Exception as exc:
            exc.add_note(f"raised by {sub._event_handler!r} while handling event {event!r}")
            raise
```

`atrigger_event` is the same loop with `await ...ahandle(...)`. The two loops share `_snapshot` and
`_claim` (the `once` check); the `try`/`except` is small enough to repeat (D5).

Methods after the change:

| Method                                       | Behaviour                                                                          |
| -------------------------------------------- | ---------------------------------------------------------------------------------- |
| `add_event_handler(event, handler, *, once)` | Registers, returns the `Subscription`.                                             |
| `on(event, *, once)`                         | Decorator: `EventHandler(func)` registered, `func` returned unchanged.             |
| `trigger_event`, `atrigger_event`            | Dispatch (P4 to P8, P11).                                                          |
| `get_subscriptions(event)`                   | Tuple snapshot of the subscriptions, in run order. Replaces `get_event_handlers`.  |
| `events`, `__contains__`, `__len__`          | Events with a handler, membership, number of registrations.                        |
| `clear_event(event)`, `reset()`              | Remove all registrations of an event, or all. Their subscriptions become inactive. |

`repr` is `EventManager(events={'epoch_end': 2, 'batch_end': 1})`: counts per event, no user `repr`
runs, so no copy outside the lock is needed (F7).

### 3.5 What gets removed

| Removed                                                                                                                | Replaced by                                                    |
| ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `BaseEventHandler.equal`, `BaseCondition.equal`, `__eq__` of both                                                      | identity                                                       |
| `EventManager.has_event_handler`, `EventManager.remove_event_handler`                                                  | keep the `Subscription`; `get_subscriptions(event)` to inspect |
| `EventManager.last_triggered_event`                                                                                    | nothing (the caller knows which event it triggered)            |
| `EventManager.get_event_handlers`                                                                                      | `get_subscriptions` (never released)                           |
| `_OnceEventHandler`, `_unwrap`, `Subscription(remove_func, is_active_func)`                                            | the registration record                                        |
| `BaseCondition`, `CallableCondition`, `as_condition`, `AlwaysCondition`, `NotCondition`, `AndCondition`, `OrCondition` | `Condition` protocol and lambdas                               |
| `coola` dependency                                                                                                     | stdlib                                                         |

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
    "OnceCondition",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]

class BaseEventHandler(ABC):
    def handle(self, /, **payload: object) -> None: ...        # abstract
    async def ahandle(self, /, **payload: object) -> None: ... # default: calls handle

class EventHandler(BaseEventHandler):
    def __init__(self, handler: Callable[..., object], handler_args: Sequence[Any] | None = None,
                 handler_kwargs: Mapping[str, Any] | None = None, *,
                 condition: Condition | None = None, filter_payload: bool = False) -> None: ...
    # properties: handler, handler_args, handler_kwargs, condition, filter_payload

class Subscription:
    event: str; event_handler: BaseEventHandler; once: bool; active: bool
    def remove(self) -> bool: ...
    def __enter__(self) -> Self: ...; def __exit__(self, *exc) -> None: ...

class EventManager:
    events: list[str]
    def add_event_handler(self, event: str, event_handler: BaseEventHandler, *, once: bool = False) -> Subscription: ...
    def on(self, event: str, *, once: bool = False) -> Callable[[F], F]: ...
    def trigger_event(self, event: str, /, **payload: object) -> None: ...
    async def atrigger_event(self, event: str, /, **payload: object) -> None: ...
    def get_subscriptions(self, event: str) -> tuple[Subscription, ...]: ...
    def clear_event(self, event: str) -> None: ...
    def reset(self) -> None: ...
    def __contains__(self, event: object) -> bool: ...
    def __len__(self) -> int: ...
```

The package goes from 18 exported names to 9, and `EventManager` from 14 public members to 9.

### Migration from `Unreleased` and from `0.5.0`

| Code                                                              | After                                                                                         |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `manager.has_event_handler(EventHandler(f), "e")`                 | `any(s.event_handler is h for s in manager.get_subscriptions("e"))`, or keep the subscription |
| `manager.remove_event_handler("e", EventHandler(f))`              | `subscription.remove()` (the value returned by `add_event_handler`)                           |
| `manager.remove_event_handler("e", h, missing_ok=True)`           | `subscription.remove()` returns `False` instead of raising                                    |
| `class C(BaseCondition): def evaluate(self): ...; def equal(...)` | `class C: def __call__(self) -> bool: ...`                                                    |
| `AndCondition(a, b)` / `OrCondition(a, b)` / `NotCondition(a)`    | `lambda: a() and b()` / `lambda: a() or b()` / `lambda: not a()`                              |
| `AlwaysCondition()` / `CallableCondition(f)` / `as_condition(f)`  | `None` / `f` / `f`                                                                            |
| `condition.evaluate()`                                            | `condition()`                                                                                 |
| `manager.last_triggered_event`                                    | removed                                                                                       |
| `handler.equal(other)`, `handler == other`                        | `handler is other`                                                                            |
| `get_event_handlers("e")`                                         | `[s.event_handler for s in get_subscriptions("e")]`                                           |
| `import coola` indirectly                                         | no dependency; `pip install minevent` installs one package                                    |

---

## 5. Dependents

| Place                                               | Change                                                                                                                                                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/docs/architecture.md`                         | Starts with the properties of section 1. Fix F10: reflection, "synchronous only", "no threading", conditional handlers, registration flow, `handle(**payload)`, custom manager sketch (delete it).    |
| `docs/docs/quickstart.md`                           | Delete "Event handler comparison", "Check the presence of an event handler", the equality removal examples, `last_triggered_event` (17 mentions). Add "Subscriptions" and "Conditions are callables". |
| `faq.md`, `troubleshooting.md`, `best_practices.md` | Merge into one `guide.md` plus a short FAQ of one-line answers that link into it (F11). Remove the equality workflows.                                                                                |
| `README.md`, `docs/docs/index.md`                   | Features list: payload, `once`, subscriptions, async, thread safety, zero dependencies. Replace the 14-row version table by the last three rows and a link to the changelog.                          |
| `CHANGELOG.md`                                      | Rewrite the _Unreleased_ migration section from section 4; only `0.5.0` to `main` matters since the removed names were never released.                                                                |
| `CLAUDE.md`                                         | Replace the `coola.*` rules (D11).                                                                                                                                                                    |
| `tests/`                                            | Section 8.                                                                                                                                                                                            |
| Packaging and CI                                    | Section 7, step 9.                                                                                                                                                                                    |

---

## 6. Evidence: a prototype of the core

I wrote the target `Subscription`, `EventHandler` (with `_call`) and `EventManager` of section 3 in
one file of 190 lines with minimal docstrings, and ran it next to `main` on the same machine
(Python 3.13.3, `timeit`, minimum of 5 repeats).

**Behaviour**

| Probe                                                                                   | `main`                           | Prototype          |
| --------------------------------------------------------------------------------------- | -------------------------------- | ------------------ |
| F1: one handler registered twice, `s1.remove()` called twice, then `len(manager)`       | `True`, `True`, 0 (both removed) | `True`, `False`, 1 |
| `once`, 8 threads released by a `Barrier`, 200 rounds, rounds where the handler ran ≠ 1 | 0                                | 0                  |
| Two `once` registrations of one handler, two triggers, handler calls                    | 2                                | 2                  |
| `wrapper == handler` / `handler == wrapper` (F2)                                        | `True` / `False`                 | no wrapper         |
| `import` time                                                                           | 35.5 ms (`coola.equality` 31 ms) | 9.9 ms             |
| `exc.add_note(...)` then `raise` keeps the type and the traceback                       | n/a                              | yes                |

**Speed** (ns per call, lower is better)

| Benchmark                             | `main` | Prototype | Change |
| ------------------------------------- | -----: | --------: | -----: |
| trigger, no handler                   |    287 |       189 |   -34% |
| trigger, 1 handler                    |    677 |       593 |   -12% |
| trigger, 1 handler, payload of 2 keys |    831 |       748 |   -10% |
| trigger, `filter_payload`, 3 keys     |  1,018 |       954 |    -6% |
| trigger, 10 handlers                  |  3,738 |     3,884 |    +4% |
| `add_event_handler` + `remove`        |  1,208 |       648 |   -46% |

The 10-handler case is within the noise of a laptop; the gate of section 8 allows +10%. The
prototype does not yet have the `try`/`except` of D5 in the loop; a `try` block is free when no
exception is raised in CPython 3.11+, and the gate re-measures it.

---

## 7. Changes to reach the target state

One branch and one PR per row, stacked in this order (each branch from the previous one, as
`CLAUDE.md` asks). Every PR updates the changelog with its number and has its tests.

| Step | Change                                                                                                                                                                                                                                                                                                                                                                                                                                        | Breaking                                                        |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1    | **Documents tell the truth** (F10, no code): fix the contradictions in `architecture.md`, `handle(**payload)` in `faq.md` and `architecture.md`, delete the custom-manager sketch, add the properties.                                                                                                                                                                                                                                        | no                                                              |
| 2    | **Registration record** (F1, F2): `Subscription` owns `_manager` and `_active`; delete `_OnceEventHandler`, `_unwrap`, `remove_func`, `is_active_func`. Regression test of F1, then the barrier test of P7 moves to the new claim.                                                                                                                                                                                                            | no (`Subscription.__init__` is internal)                        |
| 3    | **Error context** (F9): `add_note` in both trigger loops.                                                                                                                                                                                                                                                                                                                                                                                     | no                                                              |
| 4    | **`EventHandler._call`** (F8): one private method behind `handle` and `ahandle`.                                                                                                                                                                                                                                                                                                                                                              | no                                                              |
| 5    | **Conditions are callables** (F5): `Condition` protocol, `__call__` on the three stateful conditions, delete the other five classes and `as_condition`, `EventHandler` calls `condition()`.                                                                                                                                                                                                                                                   | yes (never released except `evaluate`/`BaseCondition` of 0.5.0) |
| 6    | **Remove `last_triggered_event`** (F6) and **one-line `repr`s** (F7). `get_event_handlers` becomes `get_subscriptions`.                                                                                                                                                                                                                                                                                                                       | yes                                                             |
| 7    | **Remove the equality API** (F3): `equal`, `__eq__`, `has_event_handler`, `remove_event_handler` on handlers, conditions and manager. Handlers are hashable again.                                                                                                                                                                                                                                                                            | yes                                                             |
| 8    | **Remove `coola`** (F4): `dependencies = []`; delete `dev/generate_versions.py`, `dev/config/package_versions.json`, `ci-test-deps`, `ci-test-code-dep`, `nightly-test-package-dep`, `lib-get-package-versions`, `bot-generate-package-versions`; the README table shrinks.                                                                                                                                                                   | yes (install and import)                                        |
| 9    | **Packaging and CI** (F13): drop `[project.optional-dependencies]`, the `autoextras` hook and `lib-get-package-extras.yaml`; `Development Status :: 3 - Alpha` and `Operating System :: OS Independent`; remove `--color yes`; delete the `min` job; add a `concurrency` group to `ci.yaml`; add a tag against `uv version --short` check to `release-pypi.yaml`; set the version in the release PR and move _Unreleased_ to a dated heading. | no                                                              |
| 10   | **Docs rewrite** (F11, F12): `guide.md` replaces three pages, quickstart rebuilt around `Subscription`, README and index updated; run the Markdown `pycon` blocks as doctests in `ci-doctest.yaml` (`pytest --doctest-glob='*.md'`).                                                                                                                                                                                                          | no                                                              |
| 11   | **Tests** (F14): replace `Tracer` with `Mock`, delete `tests/unit/utils.py` and `test_utils.py`, rewrite `CLAUDE.md` (D11), drop the tests of removed code.                                                                                                                                                                                                                                                                                   | no                                                              |

Steps 1 to 4 are safe to merge on their own. Steps 5 to 8 can be merged in one release; step 7 is
the one with the largest migration, so it comes after the others have shown that `Subscription` is
enough.

---

## 8. Tests and gates

- **Registration identity (P3).** Same handler registered twice: each subscription removes its own
  record once; `remove()` twice returns `True` then `False`; `active` after `clear_event`, `reset`
  and `once`. Must fail on `main` (`git stash push src`).
- **`once` (P7).** Deterministic barrier test between the snapshot and the claim (N threads, one
  call); `once` consumed by a false condition and by a raising handler; two `once` registrations of
  one handler run twice.
- **Dispatch (P4, P5).** Order; handler added or removed by a handler takes effect next trigger;
  a snapshot cannot be mutated through `get_subscriptions`.
- **Errors (P6).** The exception is the same object, `__notes__` has the event and the handler, the
  remaining handlers did not run.
- **Async (P8).** Mixed sync and async handlers in order; `handle` on a coroutine function raises
  `TypeError` and closes the coroutine (no `RuntimeWarning` under `filterwarnings = error`).
- **Conditions (P12).** The three built-ins against a closed form; `reset`; validation errors with
  `match`; a lambda as `condition`; a non-callable raises `TypeError`.
- **Payload (P11).** `event` and `self` as keys; `filter_payload` with `**kwargs`, with a
  non-introspectable callable, with a `functools.partial`; a clash with `handler_kwargs`.
- **Whole-output tests** for `repr` of the manager, the handler and the subscription (exact string),
  and for `get_subscriptions` (exact tuple).
- **Threads** (`tests/integration/`): add, remove, trigger and `clear_event` concurrently; a
  handler that registers and removes on the same manager; no exception and a consistent `len`.
- **Package checks** (`tests/package_checks.py`, run on the built wheel): `import minevent` imports
  no third-party package (`sys.modules` check), plus the existing `once`, payload, subscription and
  `atrigger_event` checks.
- **Doctests.** Source docstrings (exist) and, after step 10, the Markdown pages.
- **Benchmark gate.** The table of section 6 is a script in `dev/` (not in the package) run before and
  after steps 2, 3 and 5; a PR that is more than 10% slower on any row explains why.
- **Coverage.** 100% line and branch on `src/minevent`, no `# pragma: no cover`.
- **Lint and types.** `ruff check`, `ruff format --check`, `ty check` on `src` and `tests`.

---

## 9. Decisions for the maintainers

| #   | Question                                                                             | Recommendation                                                                                                                                                                                                                                                                                                      |
| --- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Drop the equality protocol, `has_event_handler`, `remove_event_handler` and `coola`? | **Yes.** `Subscription` is the identity (P3); equality cannot find lambdas, closures or bound methods and needs 31 ms of imports. Alternative if users need dedupe by value: keep both methods with `==` (no `coola`) and add ≈40 lines and the docs; arrays in `handler_args` then raise on ambiguous truth value. |
| D2  | Conditions: callables, or keep the classes?                                          | **Callables.** Keep only the three stateful classes. The five removed classes are unreleased, and a lambda gives the user the choice of short-circuit that `AndCondition` fixed.                                                                                                                                    |
| D3  | Remove `last_triggered_event`?                                                       | **Yes.** Racy, unused, costs a lock write per trigger. A user who wants it registers a handler that records it.                                                                                                                                                                                                     |
| D4  | Run a handler that was removed during the current trigger?                           | **Yes (keep the snapshot).** Symmetric with additions, simple, and a check of `active` before the call would still race with another thread. Teardown code that must not be called after `remove()` can test `subscription.active` itself.                                                                          |
| D5  | Add a note to exceptions of handlers?                                                | **Yes.** Three lines per loop, no new type, no change of fail-fast. Alternative: do nothing, and accept that the traceback does not name the event.                                                                                                                                                                 |
| D6  | Keep `handler_args` and `handler_kwargs` although `functools.partial` does it?       | **Keep.** They show up in `repr`, are the documented entry point of every example, and removing them breaks every user for no gain in the core.                                                                                                                                                                     |
| D7  | Run async handlers concurrently (`asyncio.gather`)?                                  | **No.** Sequential, in registration order (P4, P8). Concurrency is a handler choice (`gather` inside a handler).                                                                                                                                                                                                    |
| D8  | Lock the state of the stateful conditions?                                           | **No, and document it** (F15). A lock per condition costs more than the three lines it protects and does not make a periodic counter meaningful across threads. Revisit if a user reports a free-threaded failure.                                                                                                  |
| D9  | One-line `repr`s without `coola` formatters?                                         | **Yes.** `repr` is for debugging; the counts of the manager repr avoid running user `repr` under or around the lock.                                                                                                                                                                                                |
| D10 | `once` consumed even if the condition is false or the handler raises?                | **Keep.** It is the only rule that is atomic without the handler reporting a result (P7). Use a `OnceCondition` to wait for the first `True`.                                                                                                                                                                       |
| D11 | What replaces the `coola.*` rules in `CLAUDE.md`?                                    | Remove the rules about `coola.utils`, `coola.validation`, `LazySingleton` and `coola.testing.marks`. Keep the rest. Validation stays a `TypeError`/`ValueError` with a message in the function that has the argument, as in the current code (`_check_event` is the only shared helper).                            |
| D12 | Keep `__version__` lazy?                                                             | **Yes.** `importlib.metadata` alone is 17.5 ms to import; without `coola` nothing else pays it, so the lazy attribute now saves most of the remaining import time.                                                                                                                                                  |
| D13 | `get_event_handlers` or `get_subscriptions`?                                         | **`get_subscriptions`.** After D1, a user who did not keep the subscription needs it to remove a registration; `.event_handler` gives the handler.                                                                                                                                                                  |

---

## 10. Not covered

- **Priorities, wildcards, hierarchical events, event objects.** Non-goals of the architecture page.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). Worth a separate design if
  users ask; it does not change the runtime.
- **Weak references / auto-unsubscribe.** Non-goal; `with subscription:` and `remove()` cover the
  lifetime.
- **Collecting errors** (`ExceptionGroup`). Non-goal, kept as is.
- **Cross-process or persistent events**, and **offloading blocking handlers** from `atrigger_event`
  to a thread (`asyncio.to_thread` in the handler).
- **Free-threaded safety of conditions** (D8).
- **A plugin entry-point group** for handlers.

---

## Appendix: effect on the size of the package

Lines include docstrings (about 70% of the lines). Statements come from `coverage` on `main` (438);
the "after" columns are estimates from the prototype and the deleted classes, to be replaced by the
measured values in the last PR.

| Module                          |            Lines today | Expected after | Why                                                                                                                |
| ------------------------------- | ---------------------: | -------------: | ------------------------------------------------------------------------------------------------------------------ |
| `conditions.py`                 |                    590 |            180 | Protocol plus three stateful classes; no `equal`, no combinators, no wrappers                                      |
| `handlers.py`                   |                    477 |            320 | No `equal`, no `_key`, no `__eq__` paragraph; `_call` shared                                                       |
| `manager.py`                    |                    735 |            450 | No wrapper, no `_unwrap`, no `has_`/`remove_event_handler`, no `last_triggered_event`, no `_format_event_handlers` |
| `subscription.py`               |                    139 |            110 | A record with a back-reference instead of two callbacks                                                            |
| `__init__.py`                   |                     61 |             52 | 9 exported names                                                                                                   |
| **`src`**                       |              **2,002** |     **~1,110** |                                                                                                                    |
| `src` statements                |                    438 |           ~270 |                                                                                                                    |
| `tests/` (unit and integration) |                  3,251 |         ~1,900 | Tests of removed code (equality, combinators, wrapper, `Tracer`) go; the new ones of section 8 are added           |
| `docs/docs` (without `refs/`)   |                  2,492 |         ~1,300 | Three overlapping pages become one guide; quickstart loses the equality chapters                                   |
| Workflows (`.github/workflows`) | 31 files / 1,668 lines |      ~25 files | Five dependency-table workflows, `lib-get-package-extras` and the `min` job go                                     |
| Runtime dependencies            |                      1 |              0 |                                                                                                                    |
