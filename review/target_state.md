# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`520432b`, 2026-11-23), and proposes the smallest set of changes that makes every property true.
It replaces the fourth version of this review. That version is **fully merged** (#770 to #775:
documents, truthy and non-copyable manager, `active` read from the registry, validation of
`handler_args` and `handler_kwargs`, `AfterNCondition.reset`), so this version starts from the
result and does not repeat it. The package is small (1,388 lines, 287 statements, 0 dependencies)
and every gate is green. The sharp edges listed by the fourth review are gone; **what is left is one
structural duplication and its consequences**:

- there are **two ways to bind arguments** to a handler (`EventHandler(handler_args, handler_kwargs)`
  and `functools.partial`), and the first one is wrong when combined with `filter_payload`;
- there are **two places for the options of a registration**: `once` on the manager, `condition` and
  `filter_payload` on a handler object that `on` builds only to take apart;
- there is **a handler class hierarchy** (`BaseEventHandler`, `EventHandler`, two methods `handle` and
  `ahandle`) for something a plain callable already does.

There is also **one property that was missing: a cheap import (P2)**. `import minevent` loads 40
modules and takes 16 ms, and **`import logging` alone is 14.5 ms of it** (Python 3.14; it pulls in
`inspect` through `traceback` and `dataclasses`), for four `logger.debug` lines that nobody tests.

The target removes the handler classes: **a handler is any callable, and the options of a registration
are the keyword-only arguments of `add_event_handler` and `on`**. Breaking changes are accepted (the
README says the API is unstable before 1.0, and nothing is released since `0.5.0`), and the result
is smaller, faster and has fewer rules to document than what is on `main`.

Principles come from `docs/docs/architecture.md` (simplicity first, explicit over implicit,
composition, zero magic, the non-goals) and from `CLAUDE.md` (no runtime dependency, heavy imports
lazy, validation in the function that receives the argument, one behaviour per test).

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python 3.13,
Apple laptop, scripts kept outside the repository) or **[reading]** (from the code or the
documents). Nothing in `src`, `tests` or `docs` was changed by this review. The change was
prototyped in a scratch copy (section 7).

**Baseline on `main`** [verified]: `ruff check`, `ruff format --check` and `ty check` clean; 361
unit and integration tests pass in 0.4 s with 100% line and branch coverage (287 statements, 50
branches); `inv test.doctest` exits 0 and also checks the markdown pages; an AST audit of the 292
unit tests finds no `pytest.raises` without `match`, no loop, and no test with several asserts other
than the allowed state tests of `EventHandler` and `Tracer`. `import minevent` loads 40 modules
that a bare interpreter does not, in a median of 16 ms over 25 fresh interpreters (Python 3.14).

---

## 1. Properties of the sub-package

The package is two concepts (_event_, _handler_) and a _manager_ that connects them, plus the
`Subscription` that a registration returns and the plain-callable _conditions_. These are the rules.
Each design choice exists to make one of them true **by construction** instead of by discipline.
"Enforced by" names the test that enforces the property today (verified to exist); **new** marks a
clause that the change introduces and that needs a test (section 9). P1, P2, P4, P8, P13, P14 and P18 are
stated **as they must be after the change**: today each has a clause that differs (F1 to F5 and F7).
The table is the target: P1, P2, P4, P8, P13, P14 and P18 become true **after step 3** (P2 after step 5),
so `docs/docs/architecture.md` keeps today's wording of these rows until then (step 1 only fixes its
`**payload` typo).

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                                                                               | Enforced by                                                                                                                                                                                                                               |
| --- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | Small surface                | Events are strings, handlers are **plain callables**, the manager connects them. **Five exported names and `__version__`** (`EventManager`, `Subscription`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has **8** public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.          | `__all__` is reviewed in each PR; no test (trivial structure, `CLAUDE.md`)                                                                                                                                                                |
| P2  | Cheap import                 | `import minevent` is cheap and has no side effect: standard library only, and **not `logging`, `inspect`, `asyncio` or `importlib.metadata`** (`inspect` is imported when `filter_payload` is used, the version on the first access of `__version__`). It starts no thread, reads no file, emits no warning and writes no log. On `main` it loads 40 modules in 16 ms; the target loads 13 in about 6 ms (Python 3.14). | `tests/package_checks.py` (`check_no_third_party_import`, `check_lazy_imports`: `importlib.metadata`), `tests/benchmarks/test_import_benchmark.py` (time and module count, nightly gate); **new**: `logging`, `inspect`, `asyncio` absent |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                                                                                      | `..._add_event_handler_event_must_be_str`, `..._trigger_event_event_must_be_str`, `..._get_subscriptions_does_not_create_event`                                                                                                           |
| P4  | Validated at the door        | A wrong type raises `TypeError` **in the call that receives it**, with a message that names the argument and the value: the event, **the handler (must be callable)** and **the condition (`None` or callable)** of `add_event_handler` and `on`. An invalid registration leaves the manager unchanged.                                                                                                                 | `..._event_must_be_str`, `..._condition_incorrect_type`; **new**: handler not callable, `on` with a bad condition, manager unchanged                                                                                                      |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`. `active` is `True` if and only if the registration is in the manager.                                                                                                                                             | `test_subscription_remove_*`, `..._same_handler_registered_twice_*`, `test_subscription_active_*`                                                                                                                                         |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                                                                             | `..._get_subscriptions_keeps_order`, `test_subscription_remove_middle_keeps_order`, `..._atrigger_event_mixes_sync_and_async_in_order`                                                                                                    |
| P7  | Snapshot dispatch            | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                                                                                                                                                                                                | `..._added_during_dispatch_*`, `..._removed_during_dispatch_*`, `..._atrigger_event_snapshot`                                                                                                                                             |
| P8  | Fail-fast with context       | An exception of a handler propagates **unchanged** (same object, same type); the remaining handlers are skipped. It carries a note with the event and the **name of the handler (the function under a `functools.partial`)**, once per distinct pair. Building the note never runs the `repr` of user data.                                                                                                             | `..._raises_same_exception_type_and_object`, `..._adds_note`, `..._reused_exception_has_one_note`, `..._note_ignores_repr_of_arguments`, `test_add_error_note_*`; **new**: partial                                                        |
| P9  | `once` is at-most-once       | A `once` registration is removed **before** its handler is called, by an atomic claim: it runs at most once whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                                                                                                                                                                                                    | `test_once_handler_runs_once_when_snapshots_taken_before_dispatch` (barrier), `..._once_removed_when_condition_false`, `..._once_handler_raises`                                                                                          |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop. An object with `async def __call__` is a coroutine handler like a coroutine function.                                                                                                   | `..._trigger_event_coroutine_handler_raises`, `test_manager_async.py`; **new**: `async def __call__`                                                                                                                                      |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run **outside** the lock, so a handler can use the manager.                                                                                                                                                                                                                                                          | `tests/integration/test_manager_threads.py`, `..._trigger_event_runs_handler_without_lock`                                                                                                                                                |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependencies; the import is cheap (P2). A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`).                                                                                                                                                                                           | `tests/package_checks.py` (`check_no_third_party_import`, `check_lazy_imports`), `..._copy_and_pickle_raise_type_error`                                                                                                                   |
| P13 | Payload is data              | `trigger_event(event, /, **payload)` calls every handler as `handler(**payload)`. Any key is allowed (`event`, `self`). **Arguments that do not come from the payload are bound with `functools.partial`**: the manager has no second mechanism. With `filter_payload=True` only the keys the signature accepts are passed.                                                                                             | `..._payload_with_event_and_self_keys`, `..._on_filter_payload_*`; **new**: filter sees through a partial; the payload overrides a keyword bound by a partial                                                                             |
| P14 | Options are per registration | `once`, `condition` and `filter_payload` are keyword-only arguments of `add_event_handler` and `on`, with the same names, defaults and meaning in both. A condition is a `Callable[[], bool]` called once per trigger, before the handler. The built-in conditions keep per-instance state and both have `reset()`.                                                                                                     | `test_event_manager_on_*`, `test_conditions.py`; **new**: `add_event_handler` with `condition` and `filter_payload`                                                                                                                       |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                                                                                                                                                                                      | `ty` in `ci-type-checking.yaml`                                                                                                                                                                                                           |
| P16 | Fast and linear              | A trigger of one handler costs about 0.5 µs or less, each extra handler about 0.15 µs, a registration plus its removal about 1 µs or less. Registering _k_ handlers and removing them in any order costs O(_k_) in total. Not slower than today.                                                                                                                                                                        | `tests/benchmarks/` (nightly gate at 50%), including `test_subscription_remove_many_lifo_benchmark`                                                                                                                                       |
| P17 | A manager is a service       | `bool(manager)` is always `True`, empty or not, so `manager or default` means "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                                                                                                                                      | `test_event_manager_bool_*`, `test_event_manager_len_*`                                                                                                                                                                                   |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to bind arguments (`functools.partial`), one way to run a handler once (`once=True`), one way to extend (write a callable). No handler base class.                                                                                                                                                                                  | by the absence of `BaseEventHandler`, `EventHandler`, `handle`, `ahandle`; no test                                                                                                                                                        |

### Not guaranteed, and documented as such

- **Order across threads.** Two threads that trigger the same event run the handlers concurrently,
  in no defined interleaving. A handler that shares state must protect it.
- **State of conditions under threads.** `PeriodicCondition` and `AfterNCondition` update a counter
  without a lock.
- **A handler removed while a trigger is running** still runs in that trigger (P7). After `remove()`
  returns, the next trigger does not run it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A handler that returns a generator** (a `def` with `yield`) does nothing: the generator is
  never iterated. Only awaitables are detected (P10).
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  dict, `Subscription`, manager): `del manager` does not free it until the garbage collector runs.
  Call `reset()` to release the handlers at a known point.
- **A keyword bound by `functools.partial` and given again by the payload**: the payload wins, which
  is the rule of `partial` itself. A positional argument bound twice is a `TypeError` of Python.

---

## 2. Constraints on the target

1. **Simple and easy to maintain.** Fewer concepts, one way to do each thing. A change that adds code
   must remove a defect or a duplicate; the net size of `src` must go down.
2. **Breaking changes are accepted.** Migration notes go in `CHANGELOG.md`, with the PR number.
3. **No slower than today.** Benchmark gate in section 9: a row more than 10% slower needs a reason.
4. **Documented guarantees are true and tested.** Every property of section 1 names the test that
   enforces it; a property without a test is a finding.
5. **No runtime dependency, cheap import.** Standard library only, and `import minevent` loads no
   heavy module (P2). A feature that needs one (`inspect` for `filter_payload`) imports it when it is
   used. A debug log is not worth 14 ms of import.
6. **Python `>=3.11`.** `BaseException.add_note` and `typing.Self` are used.
7. **The repository follows its own rules.** `CLAUDE.md` and `CONTRIBUTING.md` are checked like code.
8. **Future state over past state.** A decision of an earlier review is reopened when a defect shows
   that it no longer holds (F1), and says so (section 10).

---

## 3. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Status         |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| F1  | **`handler_args` and `filter_payload` do not compose.** `EventHandler(f, [1], filter_payload=True)` with `def f(a, b)` and `handle(a=9, b=2)` raises `TypeError: f() got multiple values for argument 'a'`: the filter reads the signature of `f`, which does not know that `a` is already bound. With `functools.partial(f, 1)` the signature is `(b)`, the filter drops `a`, and the call is `f(1, b=2)` as the user meant. The same reason is why the docstring says "keys of `handler_kwargs` are not filtered". The standard library already binds arguments, and its signature is the one the filter needs.                                                                                                                                                                | **[verified]** |
| F2  | **Two ways to bind arguments, with their own rules.** `handler_args` and `handler_kwargs` are copied, validated (a `str` is rejected, keys must be `str`), exposed as three properties, put in the `repr`, and documented in 19 places of the README and the guide. All of it re-implements `functools.partial`, plus a conflict rule (`TypeError` when the payload repeats a `handler_kwargs` key) that `partial` does not have. About 45 lines of `EventHandler` and about 20 tests exist for it **[reading]**.                                                                                                                                                                                                                                                                | **[reading]**  |
| F3  | **The options of a registration are split in two objects.** `once` is an argument of `add_event_handler`; `condition` and `filter_payload` are arguments of `EventHandler`. The decorator `on` has all three and **builds an `EventHandler` only to hand it to `add_event_handler`**: it is the shape the API should have everywhere. A user has to remember which object owns which option, and `add_event_handler` cannot register a plain function without the wrapper (`TypeError: wrap a function with EventHandler(func)`).                                                                                                                                                                                                                                                | **[reading]**  |
| F4  | **The handler hierarchy has two methods for one idea.** `BaseEventHandler` asks a subclass for `handle`; `ahandle` defaults to `handle`; `EventHandler.handle` raises on an awaitable and `EventHandler.ahandle` awaits it. The manager calls one or the other. A callable that returns an awaitable already carries the same information, and it is how `EventHandler` decides. The extension point that the architecture page promises ("any function") is a class with two methods.                                                                                                                                                                                                                                                                                           | **[reading]**  |
| F5  | **The note of an exception names `partial`, not the function.** `_describe(EventHandler(functools.partial(f, 1)))` is `'partial'`: the user has to read the traceback to find the handler. With callables as handlers a `partial` is the normal way to bind arguments, so the note must see through it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | **[verified]** |
| F6  | **`architecture.md` has a typo in P12 (today's number) that changes the signature**: `trigger_event(event, /, payload)` instead of `trigger_event(event, /, **payload)`. The properties table is copied by hand in two places (the document and this review) and nothing checks them against each other.                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | **[verified]** |
| F7  | **`import minevent` is 3 times slower than it needs to be.** It loads 40 modules in 16 ms (median of 25 fresh interpreters, `-I`). `import logging` alone is 14.5 ms (88 modules against 41 for `threading`, and it imports `inspect`, `traceback`, `dataclasses`, `ast`), and it is used only by the `logger.debug` calls (`add`, `remove`, `trigger`, `atrigger`, `clear`) that no test covers. A lazy `inspect` alone gains nothing: **measured, still 40 modules and 15.7 ms**, because `logging` imports it. Without `logging` and with a lazy `inspect`: **13 modules, 6.0 ms**, and a trigger is 16% faster (404 ns against 477 ns). The same logs format the `repr` of the handler, arguments included, and a `repr` that raises prints a `--- Logging error ---` block. | **[verified]** |

### Measured and kept

- **`once` consumed by a false or a raising condition**, **a cancelled `atrigger_event`**, **`reset()`
  called by a handler**, **a handler registered by a running handler runs at the next trigger**:
  settled in the earlier reviews, unchanged.
- **The conditions module** (`Condition`, `PeriodicCondition`, `AfterNCondition`): validation,
  `reset`, `repr` and the stateful-condition documentation are at the target. No change.

### What already works and must not regress

- Snapshot dispatch with the handlers outside the lock (P7, P11), `RLock` so a handler can use the
  manager, and `once` claimed atomically.
- The registry is a `dict` used as an ordered set: O(1) removal, same order, and the identity hash
  of `Subscription` (no `__eq__`, pinned by `test_subscription_is_hashable_by_identity`). The
  registry is the **only** record of what is registered: `active` reads it.
- `event` and `self` as payload keys (`event` is positional-only), the awaitable check (a coroutine
  is closed, so no `RuntimeWarning`), one note per distinct pair, the manager that is truthy and not
  copyable, the lazy `__version__`.
- The non-goals (event objects, priorities, weak references, collecting errors).

---

## 4. Architecture

```text
EventManager ──registry──▶ {event: {Subscription: None, ...}}      insertion order = run order
     │                          event, handler, once, condition, payload keys
     │ trigger_event(event, /, **payload)
     ▼
for sub in get_subscriptions(event):        # tuple(dict): a snapshot, under the lock
    if sub.once and not _remove(sub):       # atomic claim (P9)
        continue
    result = sub._call(payload)             # outside the lock:
         │                                  #   condition() -> filter payload -> handler(**payload)
         ▼
    awaitable? trigger_event raises TypeError (closing a coroutine); atrigger_event awaits it
```

Two modules instead of three, no cycle, no dependency:

| Module          | Contains                                                           | Lines today |     Lines after |
| --------------- | ------------------------------------------------------------------ | ----------: | --------------: |
| `conditions.py` | `Condition` protocol, `PeriodicCondition`, `AfterNCondition`       |         222 |             222 |
| `handlers.py`   | `BaseEventHandler`, `EventHandler`, `_accepted_keywords`           |         406 | **0** (deleted) |
| `manager.py`    | `EventManager`, `Subscription`, `_accepted_keywords`, note helpers |         705 |            ~770 |

### 4.1 A handler is a callable (F3, F4, P1, P18)

`add_event_handler` takes any callable. The options move to the registration, and the `Subscription`
stores them: it is the record of the registration, so it is the right owner.

```python
class EventManager:
    def add_event_handler(
        self,
        event: str,
        handler: Callable[..., object],
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> Subscription: ...

    def on(
        self,
        event: str,
        *,
        once: bool = False,
        condition: Condition | None = None,
        filter_payload: bool = False,
    ) -> Callable[[_F], _F]: ...  # the decorator form: calls add_event_handler, returns func


class Subscription:
    # event, handler, once, condition, filter_payload: read-only properties
    # active, remove(), context manager: unchanged
    def _call(self, payload: dict[str, object]) -> object:
        if self._condition is not None and not self._condition():
            return None
        if self._payload_keys is not None:
            payload = {k: v for k, v in payload.items() if k in self._payload_keys}
        return self._handler(**payload)
```

- `_payload_keys` is computed once, at registration, by the existing `_accepted_keywords`
  (moved to `manager.py`, same behaviour, same tests).
- The two dispatch loops stay as they are, with `sub._call(payload)` instead of
  `handler.handle(**payload)`. The awaitable check moves from `EventHandler.handle` to the loop of
  `trigger_event`; `atrigger_event` awaits the result when it is awaitable.
- `on` becomes one line: `self.add_event_handler(event, func, once=..., condition=..., filter_payload=...)`.
  The options are the same in both, by construction (P14).
- `Subscription.event_handler` is renamed `Subscription.handler`.

### 4.2 Bound arguments are `functools.partial` (F1, F2, P13)

`EventHandler(f, ["a"], {"k": 1})` becomes `functools.partial(f, "a", k=1)`. Nothing is added to
`minevent`: `inspect.signature` of a partial already removes the bound parameters, so
`filter_payload` is correct for free (F1). The `handler_args` and `handler_kwargs` copy, validation,
properties, `repr` and the conflict rule all disappear (F2). The one behaviour difference is
documented in section 1: a payload key that repeats a **keyword** bound by the partial overrides it.

### 4.3 The note sees through a partial (F5, P8)

```python
def _describe(handler: Callable[..., object]) -> str:
    while isinstance(handler, functools.partial):
        handler = handler.func
    return getattr(handler, "__qualname__", type(handler).__qualname__)
```

`functools` is a light standard-library import; the import benchmark checks it.
The note stays `raised by <name> while handling the event '<event>'`, never the `repr` of the data.

### 4.4 Custom handlers are callables (F4, P18)

```python
# before: two methods, a base class
class Notify(BaseEventHandler):
    def handle(self, /, **payload): ...
    async def ahandle(self, /, **payload): ...


# after: one method, no base class
class Notify:
    def __call__(self, **payload): ...  # or `async def __call__`, awaited by atrigger_event
```

A class that wants a state (the use case of the architecture page: "handlers with complex state")
keeps its state in `self`, as before. Nothing is lost, because `EventHandler` never exposed more than
`handler(*args, **kwargs, **payload)`.

### 4.5 Documents (F6, P1)

`architecture.md` gets the properties table of section 1 (same ids, without the "Enforced by"
column) and the corrected `**payload`. The "Event Handler" and "Conditional Execution" sections are
rewritten around a callable and the options of a registration (the class hierarchy diagram goes
away). The README, the guide, the quickstart and the FAQ replace `EventHandler(...)` with the
callable and the options (about 55 occurrences).

### 4.6 Cheap import (F7, P2)

```python
# manager.py: remove `import logging`, `logger = logging.getLogger(__name__)` and the
# `logger.debug(...)` lines of add_event_handler, _remove, trigger_event, atrigger_event, clear_event


# _accepted_keywords: import where it is used
def _accepted_keywords(func: Callable[..., object]) -> frozenset[str] | None:
    import inspect  # noqa: PLC0415
    ...
```

`import minevent` then loads `threading`, `typing` and the `minevent` modules (13 new modules, 6 ms,
measured on the current code with these two edits). The two edits go together: **removing `logging`
is what makes the lazy `inspect` visible**, and the lazy `inspect` keeps the import cheap if
`logging` ever comes back. The docstring of `EventManager` loses "Registrations and triggers are
logged at the `DEBUG` level", the guide loses its Debug section, and a user who wants a trace wraps
the handler or reads `get_subscriptions(event)`. The hazards of the logs (`repr` of big or raising
arguments) disappear with them. A guard such as `sys.modules.get("logging")` would keep the logs
without the import cost, but it is magic (zero magic, architecture page) and one more branch on the
hot path (D7).

---

## 5. Public API after the change

```python
# minevent/__init__.py
__all__ = [
    "AfterNCondition",
    "Condition",
    "EventManager",
    "PeriodicCondition",
    "Subscription",
    "__version__",
]
```

| Signature                                                                            | Change                                                                  |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `BaseEventHandler`, `EventHandler`                                                   | removed (F2, F3, F4)                                                    |
| `EventManager.add_event_handler(event, handler, *, once, condition, filter_payload)` | `handler` is any callable; `condition` and `filter_payload` are new     |
| `EventManager.on(event, *, once, condition, filter_payload)`                         | unchanged signature; now the decorator form of `add_event_handler`      |
| `Subscription.event_handler`                                                         | renamed `Subscription.handler`                                          |
| `Subscription.condition`, `Subscription.filter_payload`                              | new read-only properties                                                |
| payload key equal to a keyword bound by a `partial`                                  | overrides it, instead of raising `TypeError` for a `handler_kwargs` key |
| `minevent.manager` DEBUG logs                                                        | removed (F7); `import minevent` no longer imports `logging`             |
| every other signature, every other exported name                                     | unchanged                                                               |

### Migration

| Before                                                                                 | After                                                                    |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `add_event_handler("e", EventHandler(f))`                                              | `add_event_handler("e", f)`                                              |
| `EventHandler(f, ["a"], {"k": 1})`                                                     | `functools.partial(f, "a", k=1)`                                         |
| `add_event_handler("e", EventHandler(f, condition=c, filter_payload=True), once=True)` | `add_event_handler("e", f, once=True, condition=c, filter_payload=True)` |
| `class H(BaseEventHandler): def handle(self, /, **payload)`                            | `class H: def __call__(self, **payload)`                                 |
| `async def ahandle(self, /, **payload)` in a subclass                                  | `async def __call__(self, **payload)`                                    |
| `logging.getLogger("minevent").setLevel(DEBUG)` to trace registrations                 | wrap the handler, or read `get_subscriptions(event)`                     |
| `subscription.event_handler`                                                           | `subscription.handler`                                                   |
| `EventHandler(f, handler_kwargs={"k": 1}).handle(k=2)` raising `TypeError`             | `partial(f, k=1)(k=2)` calls `f(k=2)`                                    |

The changelog entries stay under _Unreleased_: no release exists between the fourth review and this
one, and the migration section there already lists the removals since `0.5.0`.

---

## 6. Dependents

| Place                                                                                               | Change                                                                                                                                               |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/minevent/handlers.py`                                                                          | **Delete.** `_accepted_keywords` moves to `manager.py`.                                                                                              |
| `src/minevent/__init__.py`                                                                          | Remove the two exports and update the module docstring ("an event, a handler (any callable) and an event manager").                                  |
| `src/minevent/manager.py`                                                                           | Section 4.1 and 4.3. Docstrings of `EventManager`, `Subscription`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`.                     |
| `tests/unit/test_handlers.py` (728 lines)                                                           | Delete. The filter and `_accepted_keywords` tests move to `test_manager.py`; the `EventHandler` state and validation tests disappear with the class. |
| `tests/unit/test_manager*.py`, `tests/integration/`, `tests/package_checks.py`, `tests/benchmarks/` | Replace `EventHandler(f)` by `f`; one helper `Tracer` stays (it is already a callable).                                                              |
| `docs/docs/architecture.md`                                                                         | Properties table of section 1; rewrite "Event Handler", "Conditional Execution", "Extension Points" (section 4.5).                                   |
| `README.md`, `docs/docs/guide.md`, `quickstart.md`, `faq.md`, `index.md`, `get_started.md`          | Replace `EventHandler(...)` and `BaseEventHandler` (about 55 and 7 occurrences); add one `functools.partial` example in the guide.                   |
| `docs/docs/refs/*.md`                                                                               | Remove the `handlers` page and its entry in `mkdocs.yml`.                                                                                            |
| `docs/docs/guide.md` Debug section, `EventManager` docstring                                        | Remove the DEBUG-log paragraph (F7); say that `import minevent` is cheap (P2).                                                                       |
| `CHANGELOG.md`                                                                                      | Under _Unreleased_: removal of the two classes, the new options, `Subscription.handler`, the `partial` rule. PR numbers.                             |

---

## 7. Evidence

All on `main` at `520432b`, Python 3.13, Apple laptop, minimum of 5 `timeit` repeats, scripts in the
session scratchpad (not committed). The prototype is the **dispatch core only** (registry, options,
snapshot, `once`, awaitable check, note): 71 lines, no logging, no note de-duplication.

**Behaviour**

| Probe                                                             | `main`                                                | Target (prototype)                         |
| ----------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------ |
| F1: `def f(a, b)`; filter on; bind `a=1`; trigger with `a=9, b=2` | `TypeError: f() got multiple values for argument 'a'` | `f(1, b=2)`: the filter drops `a`          |
| F1: `inspect.signature(functools.partial(f, 1))`                  | not used                                              | `(b, *, c=1)` for `def f(a, b, *, c=1)`    |
| F1: `inspect.signature(functools.partial(f, b=2))`                | not used                                              | `(a, *, b=2, c=1)`                         |
| F5: `_describe(...)` of a partial                                 | `'partial'`                                           | the name of the function                   |
| a payload key repeating a keyword bound by a partial              | `TypeError` for `handler_kwargs`                      | the payload wins (`{'b': 3}` in the probe) |
| callable class as a handler, with a condition and a filter        | needs `EventHandler` and `BaseEventHandler`           | works, one `__call__`                      |

**Speed and size** (prototype of the dispatch core against `main`; the prototype has no
`logger.debug` and no note de-duplication, so its numbers are a lower bound and not a promise)

| Benchmark                           |   `main` | Prototype | Note                                                    |
| ----------------------------------- | -------: | --------: | ------------------------------------------------------- |
| `trigger_event`, 1 handler          |   492 ns |    275 ns | one call (`sub._call`) instead of `handle` then `_call` |
| `add_event_handler` then `remove()` | 1,244 ns |    498 ns | no `EventHandler` to build, no argument validation      |
| `src` lines                         |    1,388 |    ~1,040 | estimate: `handlers.py` out, +65 in `manager.py`        |

The gate is the benchmark suite (section 9), not these numbers. The prototype has no `logger.debug`,
which the target also removes (F7), so its trigger gain is realistic; the note de-duplication stays
and costs only on the error path.

**Import** (median of 25 fresh `python -I` interpreters, Python 3.14, `sys.path` set explicitly)

| Probe                                                         |        `main` | Target (current code, two edits of 4.6) |
| ------------------------------------------------------------- | ------------: | --------------------------------------: |
| modules loaded by `import minevent` beyond a bare interpreter |            40 |                                      13 |
| `import minevent`                                             |       15.8 ms |                                  6.0 ms |
| `import logging` alone / `threading, typing, abc, functools`  | 14.5 / 3.2 ms |                                not used |
| lazy `inspect` only (`logging` kept)                          |       15.7 ms |                    no gain (40 modules) |
| `trigger_event`, 1 handler, same code                         |        477 ns |                                  404 ns |

The 26 ms of the earlier reviews was a cold run; the warm figure is 16 ms.

---

## 8. Changes to reach the target state

One branch and one PR per row. Steps 2 and 3 are **stacked** (branch 3 from 2, retarget to `main`
after 2 is merged). Every PR updates the changelog with its number, has its tests, and keeps `ruff`,
`ty` and 100% coverage.

| Step | Change                                                                                                                                                                                                                                                                                                                                                      | Breaking                             |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 1    | **Fix the document** (F6): `**payload` in `architecture.md` P12 (today's number), and the properties table of this review (P1, P4, P8, P13, P14, P18 are the target; mark them "after step 3" if the document must stay true until then). Docs only.                                                                                                        | no                                   |
| 2    | **Options and callables on the registration** (F3, F5): `add_event_handler` accepts a callable, `condition` and `filter_payload`; `Subscription` gets `handler`, `condition`, `filter_payload`; `on` calls it; `_describe` unwraps a `partial`. A `BaseEventHandler` is still accepted (it is a callable branch of `_call`), so every existing test passes. | `Subscription.event_handler` renamed |
| 3    | **Delete the handler classes** (F1, F2, F4): remove `handlers.py`, `BaseEventHandler`, `EventHandler`; port the tests and the documents (section 6); the awaitable check lives in the dispatch loop.                                                                                                                                                        | `EventHandler`, `BaseEventHandler`   |
| 4    | **Rewrite the documents** (section 4.5): architecture, README, guide, quickstart, FAQ, mkdocs. Can be merged with step 3 if the reviewers prefer one PR for the break; kept apart so the code PR stays small.                                                                                                                                               | no                                   |
| 5    | **Cheap import** (F7, P2): section 4.6, a new import test, the guide and docstring. Independent of steps 2 to 4 (it touches `manager.py` and `handlers.py`; after step 3 only `manager.py`).                                                                                                                                                                | DEBUG logs removed                   |

**Status** (pull requests): step 1 #806, step 2 #807, step 3 #808 (stacked on #807), step 4 #809
(stacked on #808), step 5 #810 (stacked on #809). The prose of this document describes the state
before these pull requests.

Step 1 is safe alone. Steps 2 to 4 are the only API-breaking ones and ship in the same release. Step 5 is independent and
can go first: it makes the import benchmark a baseline for the others.

---

## 9. Tests and gates

New or changed tests (the existing ones that do not mention the removed classes stay). Each is one
behaviour, with `match` on every `pytest.raises`, and each regression test is checked to fail on
`main` with `git stash push src`.

- **Validation (P4).** `add_event_handler("e", 5)` and `on("e")(5)` raise `TypeError` with
  `match=r"handler must be callable"` (parametrize over a few non-callables); `condition=5` raises
  with `match=r"condition must be callable"`; after each failure `len(manager) == 0`.
- **Options (P14).** `condition` gates the handler; `condition` that returns `False` consumes a `once`
  registration (the existing rule); `add_event_handler` and `on` give the same `Subscription`
  properties for the same options; `Subscription.handler`, `.condition`, `.filter_payload` return
  what was given. Assert the whole `Subscription` state against a literal dict once.
- **`filter_payload` (P13, F1).** The existing tests (`keeps_accepted_keys`, `keyword_only`,
  `var_keyword_receives_everything`, `positional_only_not_passed`, `uninspectable_receives_everything`,
  the six `_accepted_keywords` tests) move to `test_manager.py` unchanged. **New**: a
  `functools.partial` with a bound positional drops the payload key of the same name (regression of
  F1, fails on `main`); a partial with a bound keyword is overridden by the payload.
- **Notes (P8, F5).** The note of a `partial` handler names the function; of a callable object, the
  class; of a lambda, `<lambda>` (existing). `_describe` is tested on its own (private functions have
  tests): function, method, partial, nested partial, callable object.
- **Async (P10).** An object with `async def __call__` is awaited by `atrigger_event` and raises the
  `TypeError` of P10 in `trigger_event` (the coroutine is closed: no `RuntimeWarning`). A sync callable
  object works in both.
- **Import (P2, F7).** A new `tests/integration/test_import.py` runs `import minevent` in a fresh
  `python -I` subprocess and asserts, parametrized, that `logging`, `inspect`, `asyncio` and
  `importlib.metadata` are not in `sys.modules` (fails on `main` for the first two), and that
  `filter_payload=True` still works afterwards. `check_lazy_imports` in `tests/package_checks.py`
  covers the same list. The import benchmark records the module count.
- **Integration** (`tests/integration/`): the thread tests pass with `f` instead of
  `EventHandler(f)`. **Add one test without any patching** that registers a stateful condition, a
  filter and a `partial` through `add_event_handler` from several threads and checks the count, as
  the existing ones do (`CLAUDE.md`: every patched unit test needs an unpatched integration test).
- **Benchmark gate.** `inv test.benchmark` before and after steps 2 and 3; a trigger row more than 10%
  slower is explained in the PR. The nightly workflow fails at 50% on a median. The row
  `test_event_handler_*` in `test_handler_benchmark.py` is replaced by a registration-with-options row.
- **Doctests.** `source .venv/bin/activate && inv test.doctest` after each step: source and markdown.
  New examples: `add_event_handler` with a `partial` and with `condition=`, a callable class, and the
  `Raises:` of `add_event_handler`.
- **Coverage.** 100% line and branch on `src/minevent`, no `# pragma: no cover`.
- **Lint and types.** `ruff check`, `ruff format --check`, `ty check` on `src` and `tests`.

---

## 10. Decisions for the maintainers

The decisions of the earlier reviews that this one **keeps** (snapshot dispatch, `once` consumed on a
false condition or a raising handler, sequential async, no lock in conditions, one-line `repr`s,
lazy `__version__`, `get_subscriptions`, note without `repr`, `dict` as an ordered set, dedupe of notes, the dispatch loops of
`trigger_event` and `atrigger_event` not shared, a condition without the payload, truthy and
non-copyable manager) are settled and not reopened. D7 **reopens** two more ("`inspect` imported at module level", PR #749, and "`logger.debug` kept"), because the
new property P2 and the measurement of F7 change the trade-off. D1 **reopens** two earlier decisions ("handlers as
plain callables" and "`handler_args` / `handler_kwargs` kept"), because F1 is a defect that the old
design can only fix by re-implementing the signature handling of `functools.partial`.

| #   | Question                                                                          | Recommendation                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Delete `EventHandler` and `BaseEventHandler`, handlers are callables?             | **Yes.** Fixes F1, removes F2, F3 and F4, deletes a 406-line module and about 20 tests, and `on` already has the target shape. Alternative: keep `EventHandler` as a thin helper that returns a `partial`: a second way to do the same thing (P18), kept only for habit. Alternative 2: keep it all and fix F1 inside `EventHandler` by binding with `partial` internally: the class is then a wrapper of a wrapper. |
| D2  | A payload key that repeats a keyword bound by a `partial`: override or error?     | **Override** (the rule of `partial`, no code, documented in section 1). An error needs a wrapper that inspects the partial, which is the code D1 removes. A positional argument bound twice is still a `TypeError`.                                                                                                                                                                                                  |
| D3  | Keep the name `add_event_handler`?                                                | **Yes.** It matches `get_subscriptions`, `clear_event`, `on`, and the documents. A rename (`subscribe`) is churn with no behaviour gain, and the arguments already change.                                                                                                                                                                                                                                           |
| D4  | Should a condition receive the payload?                                           | **No** (unchanged). `condition()` stays a function without argument; a handler that needs the payload to decide can decide itself. It is a feature, not a defect, and constraint 1 forbids a feature that only adds.                                                                                                                                                                                                 |
| D5  | Keep `Subscription` public and a context manager?                                 | **Yes.** It is the only way to remove one registration (P5) and the handle of `once`; it now also carries the options, so it is the single record of a registration.                                                                                                                                                                                                                                                 |
| D6  | One PR for the break (steps 2 to 4) or three?                                     | **Three, stacked.** Step 2 is mergeable alone and keeps every test green; step 3 is mostly deletions and test moves; step 4 is text. Each stays reviewable.                                                                                                                                                                                                                                                          |
| D7  | Drop the DEBUG logs and import `inspect` lazily, to make `import minevent` cheap? | **Yes.** 40 to 13 modules and 16 to 6 ms, no `logging` hazard, 16% faster trigger, a few lines out and 1 moved; no test covers the logs. Alternative: keep `logging` and guard the calls with `sys.modules.get("logging")`: same code size, a hot-path branch, and magic. Alternative 2: keep everything and accept 16 ms: P2 is then only "no third-party import".                                                  |

---

## 11. Not covered

- **Priorities, wildcards, hierarchical events, event objects.** Non-goals of the architecture page.
- **Typed payloads** (a `TypedDict` per event, generics on `EventManager`). Worth a separate design if
  users ask; it does not change the runtime.
- **Weak references / auto-unsubscribe, collecting errors (`ExceptionGroup`), cross-process or
  persistent events, offloading blocking handlers to a thread.** Non-goals, unchanged.
- **Free-threaded safety of conditions.** Documented limit.
- **Detecting a handler that returns a generator** (silently dropped). Rarer than the coroutine
  mistake, one more check on the hot path, and the library does not run user generators.
- **The `mkdocs` build.** The `docs` dependency group is not installed here, so the generated
  reference was not rendered; check it with `mkdocs build --strict` when step 4 is reviewed.
- **Repository tooling.** 26 workflows, the shared `.make/` directory and two task runners (`invoke`
  and `make`) are large for a 1,000-line package. They are shared with other projects, so they are
  outside this review.
- **A full implementation.** Only the dispatch core was prototyped. The docstrings, the de-duplicated notes and the 100% coverage are part of the PRs, not of this document.

---

## Appendix: effect on the size of the package

Lines include docstrings (`wc -l`); "Expected" is an estimate, the gate is the behaviour of sections 1
and 9, not the size.

| Module                                       | Lines today | Expected after | Why                                                                              |
| -------------------------------------------- | ----------: | -------------: | -------------------------------------------------------------------------------- |
| `conditions.py`                              |         222 |            222 | unchanged                                                                        |
| `handlers.py`                                |         406 |              0 | deleted; `_accepted_keywords` (about 35 lines with its docstring) moves          |
| `manager.py`                                 |         705 |           ~770 | options and properties of `Subscription`, `_accepted_keywords`, `_describe` loop |
| `__init__.py`                                |          55 |            ~50 | two exports out                                                                  |
| **`src`**                                    |   **1,388** |     **~1,040** |                                                                                  |
| `src` statements                             |         287 |           ~215 | the validation of `handler_args` and `handler_kwargs`, `handle`, `ahandle` out   |
| `tests/` (unit, integration, package checks) |       3,036 |         ~2,600 | `test_handlers.py` (728) out, about 300 lines of tests moved or added            |
| `docs/docs`                                  |       1,488 |         ~1,420 | handler class sections out, properties table in                                  |
| Runtime dependencies                         |           0 |              0 |                                                                                  |
| `import minevent`                            |       16 ms |          ~6 ms | `logging` out, `inspect` lazy (F7)                                               |
