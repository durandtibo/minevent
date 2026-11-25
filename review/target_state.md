# `minevent`: target state and the changes to reach it

This document defines the properties of `minevent`, compares them with the code on `main`
(`99c4c72`, #849), and proposes the changes that make every property true. It replaces the previous
version, which was written before the `Context` (#840 to #849) and no longer describes the package.

The aim in one line: **a wrong registration fails when it is made, never silently and never at the
first trigger.** The design stays: an event is a string, a handler is a callable, the manager
connects them, the `Subscription` is the registration, the `Context` is the payload. What is wrong
today is at the edges of that design: the rule that decides how to call a handler guesses when the
signature is ambiguous, and nothing checks on a pull request that the programs outside the unit
tests still run.

Items are tagged **[verified]** (reproduced with a script or a measurement on `main`, Python
3.14.10, Apple laptop, prototypes kept outside the repository) or **[reading]** (from the code, the
documents or the workflows). This change touches this document only: nothing in `src`, `tests` or
`docs` is modified.

**Baseline on `main`** [verified]: `ruff check`, `ruff format --check`, `ty check` and
`inv test.doctest` are clean; 487 unit and integration tests pass in 1.1 s with 100% line and branch
coverage. **Not green** [verified]: `python tests/package_checks.py` fails, and 2 of the 35
benchmarks fail (F1).

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the **target**. Each design choice below exists to make one of them true by
construction. "Status" compares the row with `docs/docs/architecture.md` today: **same**,
**changed** (the statement changes), **fixed** (the statement is already claimed but is not true
today) or **new**.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Status  | Enforced by                                                             |
| --- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------- |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.                                                                                                                 | same    | `test_init.py`                                                          |
| P2  | Cheap import                 | `import minevent` has no side effect (no thread, file, warning or log) and uses the standard library only. It does not import `logging`, `inspect`, `asyncio`, `importlib.metadata` or **`typing`**.                                                                                                                                                                                                                                                                                                                         | changed | `test_import.py`                                                        |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                                                                                                                                                                                           | same    | `test_manager.py`                                                       |
| P4  | Validated at the door        | `add_event_handler` and `on` reject, with a `TypeError` that names the argument and the value: a non-`str` event, a non-callable handler or condition, a signature that P13 rejects, and a generator or async generator function. A rejected registration leaves the manager unchanged.                                                                                                                                                                                                                                      | changed | `add_event_handler`, `_needs_context`, `test_manager.py`                |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` until the registration is removed, by whatever means.                                                                                                                                                                                                                                                     | same    | `Subscription`, `test_manager.py`                                       |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                                                                                                                                                                                  | same    | the ordered `dict`, `test_manager.py`                                   |
| P7  | Snapshot dispatch            | A trigger visits the registrations that exist when it starts. A registration **added** by a running handler takes effect at the next trigger. A registration **removed** before its turn does not run.                                                                                                                                                                                                                                                                                                                       | same    | `Subscription._call`, `test_manager.py`                                 |
| P8  | Fail-fast with context       | An exception of a handler or a condition propagates unchanged; the remaining handlers are skipped. It carries a note with the event and the function of the handler, once per distinct pair. No message and no `repr` of the package runs the `repr` of user data to name a handler.                                                                                                                                                                                                                                         | same    | `_describe`, `_add_error_note`, `test_manager.py`                       |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim just before its handler is called, after its condition, so it is called at most once whatever the number of threads. A false or raising condition does not consume it; a handler that raises does.                                                                                                                                                                                                                                                                       | same    | `Subscription._call`, `test_manager_once.py`, `test_manager_threads.py` |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError`. `atrigger_event` awaits the handlers one after the other. **Conditions are synchronous in both**: a condition that returns an awaitable raises `TypeError`. A coroutine that is rejected is closed.                                                                                                                                                                                                                                    | changed | `_check_not_awaitable`, `test_manager_async.py`                         |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                                                                                                                                                                                                                                                                                   | same    | `EventManager._lock`, `test_manager_threads.py`                         |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependency. A manager cannot be copied or pickled.                                                                                                                                                                                                                                                                                                                                                                                                   | same    | `__reduce__`, `test_manager.py`                                         |
| P13 | Two calls                    | A handler and a condition are called as `f()` or `f(context)`. **A parameter that has a default keeps it: the manager never fills it.** A callable whose other parameters are none is called as `f()`; one with exactly one other parameter, positional, is called as `f(context)`; any other signature (including `*args` and `**kwargs`), or one that cannot be inspected, is rejected (P4). Names and annotations are not checked. The signature is the one that `inspect.signature` reports, read once, at registration. | changed | `_needs_context`, `test_manager.py`                                     |
| P14 | Payload is data              | `trigger_event(event, context=None, /)` copies a mapping with `str` keys, or reuses a `Context` as is, into one read-only `Context` per trigger, shared by the handlers and the conditions. A `Context` can be **copied, deep-copied and pickled** if its values can. The values are not copied.                                                                                                                                                                                                                             | changed | `Context`, `test_context.py`                                            |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean. The values of a `Context` are `Any`, so the documented handlers type check in the code of a user.                                                                                                                                                                                                                                                                                                                                                                                 | changed | `ty check` in CI, a typed sample                                        |
| P16 | Fast and linear              | About 0.3 µs for a trigger with one trivial handler, 0.1 µs for each extra one, 0.7 µs with a small dict, and 4.5 µs for a registration plus its removal (the signature is inspected there, never in a trigger). Registering _k_ handlers and removing them in any order costs O(_k_).                                                                                                                                                                                                                                       | fixed   | `tests/benchmarks/`                                                     |
| P17 | A manager is a service       | `bool(manager)` is always `True`; `len(manager)` is the number of registrations.                                                                                                                                                                                                                                                                                                                                                                                                                                             | same    | `__bool__`, `test_manager.py`                                           |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to adapt a callable (wrap it in a function, a lambda or a `functools.partial` that needs nothing or only the context), one way to run once (`once=True`), one way to extend (write a callable). No handler base class. **One page states each rule.**                                                                                                                                                                                    | changed | the signatures, the documents                                           |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function, `repr(manager)` counts the registrations per event. The library logs nothing.                                                                                                                                                                                                                                                                                                                                                                                 | same    | `__repr__`, `test_manager.py`                                           |
| P20 | Everything that runs, is run | Each pull request runs the unit and integration tests, the doctests, `tests/package_checks.py` and one pass of every benchmark, so a change of the API cannot leave one of them behind.                                                                                                                                                                                                                                                                                                                                      | new     | CI (section 4.5)                                                        |

Not guaranteed, and documented as such:

- **A removal in another thread.** P7 is exact in the thread that triggers. A `remove()` from another
  thread cannot stop a handler that the trigger is about to call.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A callable object whose `__call__` is a generator**, and a function that _returns_ a generator,
  do nothing. Only generator _functions_ are rejected (P4) and awaitables detected (P10).
- **A coroutine handler registered with `once=True` and triggered with `trigger_event`** is consumed:
  the `TypeError` is raised after the call. It is a programming error that is reported loudly.
- **An optional parameter never receives the context.** `def f(context=None)` is called as `f()`
  and gets `None`, without an error: the context needs a parameter without default.
- **A decorated function** is judged by the signature that `inspect.signature` reports: with
  `functools.wraps`, that is the signature of the wrapped function.
- **An exception class that forbids new attributes** (a `frozen=True` dataclass exception) is
  replaced by the error of `add_note` [verified].
- **A mutable value of the payload** can be mutated by a handler, and the next ones see it.
- **The state of a condition under threads.** The counters are not protected.
- **Prompt reclamation.** A manager with registrations is in a reference cycle; `reset()` releases
  the handlers at a known point.

## 2. Constraints on the target

1. **Simple and easy to maintain.** No new public name, no new option. Code is added only where it
   turns a silent wrong behaviour into an error.
2. **Breaking changes are fine** (the README says the API is unstable before 1.0, and the last
   release is `0.5.0`). No alias and no deprecation period; the changelog lists them.
3. **A trigger is not slower** (P16). The cost of the new checks is paid at registration.
4. **No dependency**, standard library only, heavy imports lazy.
5. **Settled decisions stay settled** unless a defect is shown: sequential async, fail-fast, the
   snapshot, a lock in the manager and none in the conditions, the note without `repr`, a `dict` as
   an ordered set, a truthy and non-copyable manager, and the calling rule inferred from the
   signature (option A of `context_object_design.md`, narrowed by D1).

## 3. What differs today

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Property | Status     |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------- |
| F1  | **`main` is broken outside the unit tests.** `tests/package_checks.py`, which the `build` job of CI runs, fails 2 of its 9 checks (`check_payload` registers `handler(**kwargs)`, which is now called without argument; `check_async_trigger` registers `handler(value: int)`, which now receives the `Context`). `test_trigger_event_payload_benchmark` and `test_trigger_event_extra_payload_keys_benchmark` still call `trigger_event("e", epoch=1, ...)` and raise `TypeError`. Neither file is part of the unit or integration tests, and the benchmarks run on a schedule only. The CI run of `99c4c72` had not completed at the time of writing.                             | P20      | [verified] |
| F2  | **The context replaces default values.** Any positional parameter, even with a default, receives the context. With stand-ins that have the signatures of `model.train(mode=True)` (PyTorch) and `bar.update(n=1)` (tqdm): `add_event_handler("epoch_start", model.train)` calls `model.train(mode=context)` and stores a `Context` as the training mode. `bar.update` (`def update(self, n=1)`) raises `TypeError` at the first trigger. The closure idiom `lambda i=i: out.append(i)` appends three `Context` objects instead of `0, 1, 2`. As a condition, `lambda flag=flag: flag` with `flag=False` returns the context, so the handler runs whenever the payload is not empty. | P4, P13  | [verified] |
| F3  | **An async condition is always true.** `async def never(): return False` returns a coroutine, which is truthy: the handler runs in `trigger_event` and in `atrigger_event`, and Python warns that the coroutine was never awaited.                                                                                                                                                                                                                                                                                                                                                                                                                                                  | P10      | [verified] |
| F4  | **A generator handler silently does nothing**, in both triggers, for `def` and `async def` with `yield`. Only the synchronous case is listed as a limit.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | P4       | [verified] |
| F5  | **A handler that can never be called is accepted.** Two required positional parameters, or a required keyword-only parameter, register without error and raise at the first trigger, which for `training_end` can be hours later.                                                                                                                                                                                                                                                                                                                                                                                                                                                   | P4       | [verified] |
| F6  | **Registration fails on Python 3.14+ for a valid handler.** `inspect.signature` evaluates annotations there, so a function annotated with a name imported under `TYPE_CHECKING` (without `from __future__ import annotations`) raises `NameError` in `add_event_handler`. A return annotation is enough: `def f() -> Decimal`.                                                                                                                                                                                                                                                                                                                                                      | P4       | [verified] |
| F7  | **A `Context` cannot be pickled or deep-copied** (`TypeError: cannot pickle 'mappingproxy' object`). A handler cannot snapshot the payload with `copy.deepcopy`, or send it to a worker process.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | P14      | [verified] |
| F8  | **Typed handlers do not type check.** With `def handler(context: Context)`, `context["epoch"] + 1` and `context.get("loss", 0.0) * 2` are `ty` errors, because the values are `object`. Each handler needs an `isinstance` or a cast.                                                                                                                                                                                                                                                                                                                                                                                                                                               | P15      | [verified] |
| F9  | **Stale statements.** The thread-safety section of `architecture.md` says "Handlers added or removed during a trigger take effect on the next trigger", the opposite of P7. `CHANGELOG.md` says the same in the migration list, says that a payload key overrides a bound keyword, and describes `Condition` as `Callable[[], bool]` in two entries. P16 gives 0.65 µs for a registration plus its removal; it measures 3.4 µs.                                                                                                                                                                                                                                                     | P18      | [verified] |
| F10 | **The documents repeat the rules.** `docs/docs` has 2,102 lines for 271 statements. The calling rule, the read-only `Context` and `once` are each explained in four or more pages, and #849 had to edit the README, the changelog and five pages. F9 is the result.                                                                                                                                                                                                                                                                                                                                                                                                                 | P18      | [verified] |
| F11 | **Tests against `CLAUDE.md`.** `EventManager._remove` has no test of its own; `test_event_manager_atrigger_event_without_event_handler` has no assertion; `test_event_manager_trigger_event_condition_reads_the_payload` has a loop.                                                                                                                                                                                                                                                                                                                                                                                                                                                | -        | [verified] |
| F12 | **The import loads `typing` to read a constant.** `from typing import TYPE_CHECKING` is the only runtime use. The previous review proposed to remove it; it is not on `main`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | P2       | [verified] |

What is already right and must not regress: callables as handlers and conditions; one `Context` per
trigger, shared and read-only; the keyword-only options owned by the `Subscription`; the atomic
`once` claim after the condition; a removed registration never starts; the note that names the
function; the lazy `inspect` and `__version__`; 100% coverage.

## 4. Target design

### 4.1 Two calls (P4, P13)

A handler is written as `def g()` or `def g(context: Context)`, and any callable that can be called
in one of these two ways works: **the parameters that have a default are ignored.** `model.train`
(`def train(self, mode=True)`) is called as `model.train()`. To set a default, wrap the call:
`lambda: model.train(mode=True)`. Conditions follow the same rule, with a boolean result. The same
function checks both, once, at registration.

| Parameters without default            | Example                            | Today            | Target       |
| ------------------------------------- | ---------------------------------- | ---------------- | ------------ |
| none: no parameter                    | `def g()`                          | `g()`            | `g()`        |
| none: only positional with defaults   | `model.train`, `lambda i=i: ...`   | `g(context)`     | `g()`        |
| none: only keyword-only with defaults | `def g(*, v=1)`, `partial(f, v=1)` | `g()`            | `g()`        |
| one, positional                       | `def g(context)`                   | `g(context)`     | `g(context)` |
| one, positional, then defaults        | `def g(context, verbose=False)`    | `g(context)`     | `g(context)` |
| `*args`, with or without `**kwargs`   | `print`, `Mock()`, `AsyncMock()`   | `g(context)`     | `TypeError`  |
| `**kwargs`                            | `def g(**kw)`                      | `g()`            | `TypeError`  |
| cannot be inspected                   | `max`, `dict.update`               | `g(context)`     | `TypeError`  |
| two or more                           | `def g(a, b)`                      | fails at trigger | `TypeError`  |
| one, keyword-only                     | `def g(*, epoch)`                  | fails at trigger | `TypeError`  |
| generator or async generator function | `def g(): yield`                   | does nothing     | `TypeError`  |

Coroutine functions, bound methods, callable objects, classes and `functools.partial` objects follow
the same table. The core of the prototype (the docstring is omitted):

```python
def _needs_context(func: Callable[..., object], name: str) -> bool:
    import inspect  # noqa: PLC0415

    if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
        msg = f"{name} must not be a generator function, but got {_describe(func)}"
        raise TypeError(msg)
    options = {}
    if sys.version_info >= (3, 14):  # do not evaluate the annotations (F6)
        import annotationlib  # noqa: PLC0415

        options["annotation_format"] = annotationlib.Format.FORWARDREF
    msg = (
        f"{name} {_describe(func)} must need no argument or only the context; "
        "wrap it in a function or a lambda"
    )
    try:
        parameters = inspect.signature(func, **options).parameters.values()
    except (TypeError, ValueError) as exc:
        raise TypeError(msg) from exc
    # The parameters that have a default keep it: only the others need a value.
    required = [param for param in parameters if param.default is param.empty]
    if not required:
        return False
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(required) == 1 and required[0].kind in positional:
        return True
    raise TypeError(msg)
```

Examples:

```python
manager.add_event_handler("epoch_start", model.train)  # model.train()
manager.add_event_handler("epoch_start", lambda: model.train(mode=True))  # a chosen value
manager.add_event_handler("batch_end", bar.update)  # bar.update()
manager.add_event_handler("e", lambda context: print(context))  # print
manager.add_event_handler("e", lambda: print("Hello!"))  # partial(print, "Hello!")
manager.add_event_handler("e", functools.partial(save, "model.pt"))  # save(path, context)
```

In a test, `unittest.mock.create_autospec(func)` replaces `Mock()`: it has the signature of `func`
[verified]. `on` applies the rule when the decorator is applied, as it applies the callable check
today.

#### The default-argument idiom (`lambda i=i`)

A lambda created in a loop reads the loop variable when it is **called**, so every lambda sees the
last value:

```python
handlers = [lambda: print(i) for i in range(3)]
for handler in handlers:
    handler()  # prints 2, 2, 2
```

A default value is evaluated when the function is **created**, so `i=i` stores the current value in
a parameter of the lambda. The left `i` is that parameter, the right `i` is the loop variable. The
author expects a call **without argument**, so that the default is used:

```python
for i in range(3):
    manager.add_event_handler("e", lambda i=i: print(i))
manager.trigger_event("e")
```

| Code                                               | `main`                                   | Target                 |
| -------------------------------------------------- | ---------------------------------------- | ---------------------- |
| the loop above                                     | prints `Context({})` three times         | prints `0`, `1`, `2`   |
| `condition=lambda flag=flag: flag`, `flag = False` | the handler runs if the payload has keys | the handler is skipped |

On `main` the manager sees a parameter and calls `handler(context)`, so the context replaces the
saved value. Nothing raises. In the condition, `flag` becomes the context, which is true when it is
not empty. In the target the default is never filled (P13).

A handler that needs a saved value **and** the context gives the context no default and puts it
first:

```python
manager.add_event_handler("e", lambda context, i=i: print(i, context["epoch"]))
```

### 4.2 A condition never returns an awaitable (P10)

In `Subscription._call`, after the condition:

```python
if result is not True and isinstance(result, Awaitable):
    if isinstance(result, Coroutine):
        result.close()
    msg = f"condition {_describe(self._condition_call)} returned an awaitable"
    raise TypeError(msg)
```

The check is on the result, so it also covers an object with `async def __call__` and a `lambda` that
returns a coroutine. A `once` registration is not consumed (the error comes before the claim). The
other results keep their truth value, so a NumPy or tensor boolean still works.

### 4.3 The `Context` (P14, P15)

```python
class Context(Mapping[str, "Any"]):
    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, object] | None = None) -> None:
        ...
        self._data = dict(data)  # was MappingProxyType(dict(data))

    def __getitem__(self, key: str) -> Any: ...
```

The context stays read-only because it has no method that changes it and `_data` is private: the
`MappingProxyType` protected a private attribute. Removing it makes the object picklable, deletes the
`types` import and makes a trigger with a dict slightly faster. `Any` for the values lets
`context["epoch"] + 1` type check; the argument of the constructor stays `Mapping[str, object]`.

### 4.4 `import minevent` loads no `typing` module (P2)

`TYPE_CHECKING = False` in `manager.py` and `context.py` replaces the import from `typing`. Type
checkers recognise the idiom.

### 4.5 Gates that stop the drift (P20)

- Fix `tests/package_checks.py`: the two handlers take the context.
- Fix the two benchmarks: pass a dict.
- Add `tests/integration/test_package_checks.py`, which runs the script in a subprocess.
- Run each benchmark once on a pull request: `tests/benchmarks/conftest.py` also runs them with
  `--benchmark-disable`, and `ci-test.yaml` runs
  `pytest tests/benchmarks --benchmark-disable --ignore=tests/benchmarks/test_import_benchmark.py`
  (0.2 s [verified]; the import benchmarks need the statistics, so they stay scheduled).
  `.github/GUIDELINES.md` is updated with the step.

### 4.6 One home per fact (P18)

| Page              | Holds                                                                | Change                                      |
| ----------------- | -------------------------------------------------------------------- | ------------------------------------------- |
| `architecture.md` | the properties, the limits, the calling-rule table, the design notes | the only normative page; drop the restating |
| `quickstart.md`   | the first contact: register, trigger, payload, remove                | cut from 620 lines to about 200             |
| `examples.md`     | the runnable recipes                                                 | gains the unique recipes of the others      |
| `guide.md`        | the recommendations, pitfalls and troubleshooting                    | no recipe, no restated rule                 |
| `faq.md`          | nothing that is not elsewhere                                        | **deleted**                                 |
| docstrings        | signature, `Args:`, `Returns:`, `Raises:`                            | unchanged role                              |
| `README.md`       | what it is, install, one example                                     | the feature list links instead of explains  |

The "Unreleased" section of `CHANGELOG.md` is rewritten **against `0.5.0` only**: one migration list
and one feature list, without the intermediate states that were never released.

## 5. Public API after the change

No name, method or option is added or removed.

```text
from minevent import (
    AfterNCondition,
    Condition,  # Callable[[], bool] | Callable[[Context], bool]
    Context,  # Mapping[str, Any]
    EventManager,
    PeriodicCondition,
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

| Before                                                    | After                                                      |
| --------------------------------------------------------- | ---------------------------------------------------------- |
| `def f(context=None)`, receiving the context              | `def f(context)`, or register `lambda context: f(context)` |
| `lambda i=i: ...`, where `i` received the context         | unchanged code, now called as `f()`                        |
| `add_event_handler("e", print)`                           | `lambda context: print(context)`                           |
| `functools.partial(print, "Hello!")`                      | `lambda: print("Hello!")`                                  |
| `def f(*args)`, `def f(**kwargs)`                         | `def f(context)` or `def f()`                              |
| an uninspectable callable (`max`, `dict.update`)          | `lambda context: ...`                                      |
| `Mock()` or `AsyncMock()` as a handler                    | `create_autospec(func)`                                    |
| a handler with two required parameters (it always raised) | bind all but the context with `functools.partial`          |
| an async condition (it was always true)                   | compute the value before the trigger, pass it in           |
| a generator handler (it did nothing)                      | a function that iterates                                   |
| `isinstance` or casts on context values for the checker   | not needed any more                                        |

## 6. Evidence

A prototype of 4.1, 4.2 and 4.3 in a scratch copy of `src`, run against the existing suite and the
documents.

**Behaviour** [verified]:

| Probe                                            | `main`                      | Prototype                   |
| ------------------------------------------------ | --------------------------- | --------------------------- |
| `model.train` as a handler                       | mode set to a `Context`     | `train()`: mode is `True`   |
| `lambda i=i` registered for `i` in 0, 1, 2       | three `Context` objects     | `0, 1, 2`                   |
| condition `lambda flag=flag: flag`, `flag=False` | the handler runs            | the handler is skipped      |
| `def f(context=None)`                            | receives the context        | receives `None`             |
| `functools.partial(model.train, mode=True)`      | called without argument     | same                        |
| `print`, `Mock()`, `AsyncMock()`, `max`          | receive the context         | `TypeError` at registration |
| `create_autospec(func)`, a callable object       | follow their signature      | same                        |
| async condition returning `False`                | the handler runs            | `TypeError` at the trigger  |
| generator and async generator handlers           | nothing happens             | `TypeError` at registration |
| `def f() -> Decimal` (`TYPE_CHECKING` import)    | `NameError` at registration | registered (3.14 and 3.15)  |
| `copy.deepcopy` and `pickle` of a `Context`      | `TypeError`                 | round trip                  |
| `context["epoch"] + 1` with an annotated handler | `ty` error                  | clean                       |

**What the rule breaks in the repository** [verified, prototype, with a default for the new `name`
argument of the helper]:

- 395 tests pass and 92 fail. The failures are tests of the old rule and tests whose handler has a
  rejected shape: `print` and one `(*args, **kwargs)` helper account for 68 of them.
- Examples of the README, `quickstart.md` and `guide.md` fail because they register `print`, and 4 of
  the 19 doctests of `src` (xdoctest) fail.
- No benchmark fails besides the 2 of F1.

**Speed** (Python 3.14.10, best of 7, mean of two runs) [verified]:

| Case                          | `main` (µs) | Prototype (µs) |
| ----------------------------- | ----------: | -------------: |
| trigger, no handler           |       0.186 |          0.187 |
| trigger, 1 handler            |       0.311 |          0.314 |
| trigger, 10 handlers          |       1.091 |          1.099 |
| trigger, 1 handler, dict      |       0.765 |          0.735 |
| trigger, 1 handler, `Context` |       0.326 |          0.326 |
| trigger, 1 handler, condition |       0.333 |          0.338 |
| registration plus removal     |         3.5 |            4.4 |

A trigger is unchanged within noise. A registration costs about 1 µs more, once per handler.

**Import** (median of 40 runs, over a bare interpreter) [verified]: `main` loads 23 modules in
4.9 ms; the prototype with 4.4 loads 20 modules in 3.3 ms.

Not verified: Python 3.11 to 3.13 (not installed; they do not evaluate annotations in
`inspect.signature` [reading]).

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own and stacked where
it says so.

| Step | Branch                                           | Change                                                                | Breaking | Fixes      | PR   |
| ---- | ------------------------------------------------ | --------------------------------------------------------------------- | -------- | ---------- | ---- |
| 1    | `bugfix/fix-package-checks`                      | Fix the two checks and the two benchmarks, add the gates of 4.5       | no       | F1         | #851 |
| 2    | `bugfix/forward-ref-annotations`                 | Do not evaluate the annotations on 3.14+                              | no       | F6         | #852 |
| 3    | `refactor/use-accepted-signatures` (on 2)        | Tests, docstrings and documents register only accepted shapes         | no       | -          | #853 |
| 4    | `feat/two-handler-calls` (on step 3)             | The rule of 4.1, generator functions rejected, documents of the rule  | **yes**  | F2, F4, F5 | #854 |
| 5    | `bugfix/reject-awaitable-conditions` (on step 4) | The check of 4.2                                                      | **yes**  | F3         | #855 |
| 6    | `bugfix/picklable-context`                       | A plain `dict` in the `Context`                                       | no       | F7         | #856 |
| 7    | `feat/context-values-any` (on step 6)            | `Mapping[str, Any]`, P15, a typed sample checked by `ty`              | no       | F8         | #PR  |
| 8    | `perf/import-without-typing` (on step 7)         | `TYPE_CHECKING = False`, `typing` in `LAZY_MODULES`                   | no       | F12        | -    |
| 9    | `test/follow-the-test-rules`                     | Tests of `_remove`, the missing assertion, the loop                   | no       | F11        | -    |
| 10   | `docs/one-home-per-fact` (last)                  | The table of 4.6, the changelog, the timings and the stale statements | no       | F9, F10    | -    |

Step 1 comes first: `main` is broken and the other steps need its gates. Step 3 passes on `main` as
it is, so the breaking pull request (step 4) stays small. Each step updates the docstrings, the
property it changes in `architecture.md` and the changelog; step 10 only removes duplication and
fixes what is left. If only part is taken, take **1 to 5**: they are the ones where a user gets a
wrong result today.

## 8. Tests and gates

One behaviour per test, `match` on every `pytest.raises`, literals for expected values.

| Test (module)                                                        | Behaviour                                                       |
| -------------------------------------------------------------------- | --------------------------------------------------------------- |
| `test_package_checks_pass` (integration)                             | the script exits with 0                                         |
| `test_needs_context_*` (`test_manager.py`, parametrized)             | each row of the table of 4.1, with the argument name in `match` |
| `test_add_event_handler_rejected_signature_leaves_manager_unchanged` | `pytest.raises` then `len(manager) == 0`                        |
| `test_needs_context_unresolved_annotation`                           | a function with an undefined annotation is inspected            |
| `test_trigger_event_condition_returns_awaitable`                     | `TypeError`, the handler is not called                          |
| `test_trigger_event_condition_awaitable_keeps_once_registration`     | `subscription.active` stays `True`                              |
| `test_atrigger_event_condition_returns_awaitable`                    | the same through `atrigger_event`                               |
| `test_trigger_event_condition_truthy_non_bool`                       | `1` runs the handler                                            |
| `test_context_pickle` / `test_context_deepcopy`                      | equal context, deep-copied values                               |
| `test_context_does_not_copy_the_values` (kept)                       | unchanged                                                       |
| `test_import_minevent_does_not_import_module[typing]`                | replaces the five tests of the `typing` names                   |
| `test_remove_*` (`test_manager.py`)                                  | `_remove`: removed, already removed, last one drops the event   |

The tests of the old rule are rewritten. Each regression test must **fail on `main`**
(`git stash push src`). Gates before each merge: `ruff check src tests`, `ruff format src tests`,
`ty check`, `pytest tests/unit tests/integration --cov=minevent --cov-branch` at 100%,
`inv test.doctest`, `python tests/package_checks.py`, one pass of the benchmarks, and the benchmarks
compared with `main` for steps 4, 5 and 6 (P16).

## 9. Decisions for the maintainers

- **D1. How is a callable called?** _Decided: as `f()` or `f(context)`, and a parameter that has a
  default keeps it._ `model.train`, `bar.update`, the `lambda i=i` idiom and keyword `partial` work
  as written. The cost: `def f(context=None)` is called without the context and without an error.
  Alternatives that were considered: reject every optional parameter (`model.train` then needs a
  wrapper), or fill the first one with the context (today).
  - _To confirm:_ `*args` and `**kwargs` are rejected, because neither says whether the context is
    expected, so `print` and `Mock()` need a wrapper. Alternative: ignore them like the parameters
    that have a default; `print` is then called without argument and prints an empty line.
- **D2. Drop the inference and always call `handler(context)`?**
  _Recommended: no._ It deletes `inspect` and the whole rule, but every handler without data becomes
  `lambda _: ...`.
- **D3. Await async conditions in `atrigger_event`?**
  _Recommended: no._ It gives conditions two contracts. A handler can await and decide.
- **D4. Type the context values as `Any`?**
  _Recommended: yes._ `object` makes the user write casts that check nothing at run time. Alternative:
  keep `object` and show `isinstance` narrowing in every typed example.
- **D5. `TYPE_CHECKING = False`?** _Recommended: yes_, one line per module for a third of the import
  cost. Alternative: keep the usual idiom; if so, remove `typing` from this target (P2).
- **D6. Add the event name to the `Context`?** _Recommended: no._ A reused `Context` would need a copy
  per trigger. A handler registered on several events binds the name with `functools.partial`.
- **D7. Merge `reset()` into `clear_event(None)`, or shorten `add_event_handler`?**
  _Recommended: no._ A rename breaks every user and fixes nothing.
- **D8. Reject a coroutine handler in `trigger_event` before the `once` claim?** _Recommended: no._
  It adds a second detection of coroutines for an error that is already loud.
- **D9. Delete `faq.md`?** _Recommended: yes._ Alternative: keep it as a list of links.

## 10. Not covered

- **The non-goals of the architecture page** (event objects, priorities, wildcards, weak references,
  collecting errors) and concurrent async dispatch: unchanged.
- **Return values of handlers**: `trigger_event` returns `None`.
- **Typed payloads** (a `TypedDict` per event): needs its own design if users ask.
- **Static types of the two calls** (`Callable[[], object] | Callable[[Context], object]` for
  the handler argument), so that a type checker reports a wrong signature: not prototyped.
- **`_check_event`** is a validator of one `isinstance`, which `CLAUDE.md` discourages. It has four
  callers, so inlining it would repeat the message four times. It is kept.
- **Scheduled workflows.** The `Benchmark` workflow failed on 2026-11-24 and 2026-11-25 with
  "Performance has regressed"; the cause was not analysed. It compares with the last successful run,
  so an intended change of cost keeps failing. The nightly package tests install the published
  package and run the checks of `main`, so they are expected to fail until a release [reading]. Both
  deserve their own change.
- **Shared tooling** (`.make/`, `dev/`, the `bot-` workflows).
- **A full implementation.** Only the core of steps 2 and 4 to 8 was prototyped. The docstrings, the
  documents and the final tests belong to the pull requests.

---

## Appendix: effect on the size of the package

| Item                 |            Today | Expected after | Why                                              |
| -------------------- | ---------------: | -------------: | ------------------------------------------------ |
| `manager.py` (lines) |              961 |         ~1,000 | the strict rule, the awaitable check, docstrings |
| `context.py` (lines) |               86 |            ~90 | `Any` under `TYPE_CHECKING`                      |
| `src` statements     |              271 |           ~290 | the branches of the rule                         |
| public names         | 6, `__version__` |      unchanged |                                                  |
| `docs/docs` (lines)  |            2,102 |         ~1,500 | `faq.md` deleted, `quickstart.md` cut            |
| runtime dependencies |                0 |              0 |                                                  |
| `import minevent`    |           4.9 ms |        ~3.3 ms | no `typing` module                               |
