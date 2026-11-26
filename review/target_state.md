# `minevent`: target state and the changes to reach it

This document describes the design that `minevent` should have, then the changes to make to the
current implementation (`main`, `0ca7459`, #905) to get there. The design follows the properties of
the "How It Works" page (`docs/docs/architecture.md`), the reasons of the "Design Choices" page
(`docs/docs/design.md`) and the rules of `CLAUDE.md`. It replaces the previous version, whose steps
were merged (#894 to #905) except two: step 6 was dropped, and step 12, which removed the tests from
the source distribution, was closed on purpose (#906): the source distribution ships the tests
(D4).

The aim in one line: **a small library whose every stated guarantee is true, with each rule written
once.**

The design stays: an event is a string, a handler is a callable, the manager connects them, the
`Subscription` is the registration, the `Context` is the payload, a condition is a function. One
rule changes: a handler and a condition are always called as `f(context)`, and a signature that does
not fit is rejected at registration (D2). The review found no defect in the dispatch. The rest is at
the edges: guarantees that are stated too strongly, one unbounded message, and the upkeep of the
documentation, the tests and the repository. The target adds one property, the `step` of the
condition, and no concept, class or exported name.

Items are tagged **[verified]** (reproduced with a script, a test run, a measurement or a read of the
GitHub API, on an Apple laptop; scripts and prototype kept outside the repository) or **[reading]**
(from the code, the documents or the workflows). This change touches this document only: nothing in
`src`, `tests`, `docs` or `.github` is modified.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the **target**. Each design choice below exists to make one of them true by
construction, or to say exactly where it stops. "Status" compares the row with `main`: **same**
(stated and true today), **changed** (the statement changes) or **fixed** (claimed, or expected from
a claim, but not true today).

### Surface and registration

| #   | Property              | Statement                                                                                                                                                                                                                                                                                                                                                                                    | Status  | Enforced by                           |
| --- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------- |
| P1  | Small surface         | Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Handler`, `Condition`, `PeriodicCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `in`. **The public API is what `minevent` exports**: the other names of its modules can change. | changed | `__all__`, the reference pages        |
| P2  | Standard library only | No runtime dependency. `import minevent` starts no thread, emits no warning and writes no output and no log. Plain imports at the top of the modules; the import time is not a design input.                                                                                                                                                                                                 | same    | `package_checks.py`, `test_import.py` |
| P3  | Events are strings    | An event name is a case-sensitive `str` (a `StrEnum` member is one, and is kept as given). The methods of the manager raise `TypeError` for another type, and `in` answers like a dict. The empty string is valid. Reading the manager never creates an event.                                                                                                                               | same    | `_check_event`                        |
| P4  | Validated at the door | Every argument is checked by the function that receives it: `TypeError` for a wrong type, `ValueError` for a wrong value. `once` is a `bool`; the integers of a condition are an `int` but not a `bool`. A callable that cannot be called as documented is rejected. A rejection leaves the manager as it was.                                                                               | same    | `add_event_handler`, `calls`          |
| P5  | One call              | A handler and a condition are always called as `f(context)`. Exactly one parameter lacks a default, and it is positional; the others keep their default. Anything else is rejected at registration. Names and annotations are not checked. The signature is read once.                                                                                                                       | changed | `calls.check_signature`               |

### Dispatch

| #   | Property               | Statement                                                                                                                                                                                                                                                           | Status | Enforced by                         |
| --- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ----------------------------------- |
| P6  | Registration identity  | `add_event_handler` returns a new `Subscription` every time. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` exactly while the registration is in the manager, and a `Subscription` cannot be copied or pickled. | same   | `Subscription`, `EventManager`      |
| P7  | Order                  | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                         | same   | the ordered `dict`                  |
| P8  | Snapshot, removal wins | A trigger visits the registrations that exist when it starts. An addition waits for the next trigger. A registration removed before its handler is called does not run, whoever removed it.                                                                         | same   | `Subscription._claim`               |
| P9  | `once` is at-most-once | A `once` registration is removed by an atomic claim after its condition and just before its handler. A false or raising condition does not consume it; a handler that raises does.                                                                                  | same   | `Subscription._claim`               |
| P10 | Synchronous by default | `trigger_event` never awaits: a coroutine function as handler in the snapshot raises `TypeError` before anything runs, and any other awaitable result raises it after the call. `atrigger_event` awaits one handler at a time. Conditions are synchronous.          | same   | `trigger_event`, `reject_awaitable` |

### Errors, payload, threads

| #   | Property                | Statement                                                                                                                                                                                                                                                                                                                   | Status  | Enforced by                        |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------- |
| P11 | Fail-fast, never masked | An exception of a handler or a condition propagates unchanged, with a note that names the event and what raised, and the next handlers are skipped. Adding the note and naming the callable never raise instead of it. **One exception comes from Python: a `StopIteration` leaves `atrigger_event` as a `RuntimeError`.**  | fixed   | `calls.add_error_note`, `describe` |
| P12 | Bounded messages        | A message or a note of `minevent` is short whatever the size of the user data, the event name and **the arguments of a condition** included: values are shown with `reprlib`, and a missing key lists at most 20 keys.                                                                                                      | fixed   | `reprlib`, `calls.describe_event`  |
| P13 | Payload is data         | One read-only `Context` per trigger, shared by the handlers and the conditions, from a mapping with `str` keys or a `Context` used as is. The keys that are checked are the keys that are stored. `Context` is final.                                                                                                       | same    | `Context`, `typing.final`          |
| P14 | Thread-safe registry    | The registry is protected by a lock against the other **threads**. Handlers, conditions, `repr` and the finalizers of the removed handlers run outside it. This holds with and without the GIL. **Code that interrupts a method of the manager in the same thread, such as a signal handler, must not change the manager.** | fixed   | `EventManager._lock`               |
| P15 | Exact condition         | `PeriodicCondition` counts every call once, from any number of threads, and can be copied and pickled. **`step` reads the count that its `repr` shows.**                                                                                                                                                                    | changed | the counter lock                   |
| P16 | Explicit, no state      | No global manager, no discovery, no side effect of a read. A manager is always truthy, has no length, and cannot be copied or pickled. The library logs nothing. **`repr` of a subscription shows what decides whether it runs.**                                                                                           | changed | `__reduce__`, `__repr__`           |

### Engineering

| #   | Property          | Statement                                                                                                                                                                                             | Status  | Enforced by                 |
| --- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | --------------------------- |
| P17 | Typed             | Fully typed, `py.typed`, `ty check` clean, no cast and no ignore. A handler argument is typed `Handler`, so a type checker reports a function without parameter. The values of a `Context` are `Any`. | changed | `ty check`                  |
| P18 | Fast and linear   | About 0.3 µs for a trigger with one trivial handler, 0.07 µs for each extra one, 0.8 µs with a small dict, 5.5 µs for a registration plus its removal. A removal is O(1).                             | same    | `tests/benchmarks/`         |
| P19 | One home per rule | One documentation page states each rule; a docstring states what its own object does and names the page or the function that holds the rule. The other pages link to it.                              | fixed   | review                      |
| P20 | Layered           | `manager` imports `conditions` and `calls`, which import `context`. The two middle modules do not import each other. A new module must be placed in a layer.                                          | fixed   | `lint-imports`, exhaustive  |
| P21 | Tested systems    | The tests run on Linux and macOS and on every supported Python. Windows is not supported.                                                                                                             | same    | `ci.yaml`                   |
| P22 | Lean to maintain  | Every file and every dependency of the repository serves a property of this table.                                                                                                                    | fixed   | review, `pyproject.toml`    |
| P23 | Testable release  | The source distribution holds the tests of the package, in the layout of the repository, and they pass from it. It does not hold `dev/` or the test of `dev/`. The wheel holds the package only.      | fixed   | `pyproject.toml` (CI: #910) |

Not guaranteed, and documented as such (**new** marks an item that the documentation does not list
today, or lists wrongly):

- **A removal in another thread** cannot stop a handler whose trigger has already passed the check.
- **A signal handler or a garbage collection finalizer** can interrupt a method of the manager. One
  that adds, removes or triggers a `once` registration can make `remove()` raise, or leave a
  subscription `active` that is not registered. Set a flag in it, and use the manager in the main
  code. (**new**)
- **Concurrent calls.** A registration without `once` is called by every thread that triggers its
  event, possibly at the same time. The state of a user handler or condition is its own concern.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **`StopIteration` in `atrigger_event`.** Python turns it into a `RuntimeError`, whose
  `__cause__` is the original exception and has the note. (**new**)
- **The start of a coroutine.** `atrigger_event` reads the registrations and copies the payload when
  its coroutine starts to run.
- **A hidden coroutine** (a lambda, a `functools.cache`, a synchronous `functools.wraps` wrapper) is
  only detected after its call by `trigger_event`.
- **Hidden generators**, synchronous or **asynchronous** (**new**): a function that returns one does
  nothing.
- **Names are not checked.** An unbound method `Model.save` is called with the context as `self`.
- **A signature that depends on Python.** `set().add` and `time.sleep` are rejected on 3.11 and
  3.12 and accepted from 3.13. (**new**: the page names `set.add`, which is rejected on every
  version)
- **A condition is evaluated by truthiness**, and it counts its calls, not the triggers.
- **A mutable value of the payload** can be mutated by a handler.
- **A huge integer** (more than 4,300 digits) raises the `ValueError` of Python when `minevent` has
  to show it, on 3.11 and 3.12.
- **Delayed release.** A manager with registrations is in a reference cycle; `reset()` releases the
  handlers at a known point.

## 2. Constraints on the target

1. **Simple and easy to maintain.** No new concept. A change that costs more code or text than the
   problem it solves is rejected (D1).
2. **Breaking changes are fine.** PyPI has `0.5.0` and `main` is `0.6.0a0` [verified]. No alias and
   no deprecation period; the changelog follows. The future state matters more than the past one.
3. **Standard library only** (P2).
4. **A trigger does not get slower.** Only the one call (4.7) changes the trigger, and its prototype
   costs the same (section 10).
5. **Decisions of the maintainer stay**: one call, checked; Linux and macOS only; `int` only for the
   integer arguments; no `workflow-config.json`; no aggregate `ci` job; benchmarks nightly only;
   plain imports; the tests in the source distribution but not in the wheel, without `dev/`; and the
   check of the cyclic imports.
6. **Settled designs without a defect stay**: sequential async, fail-fast, the snapshot, the check of
   the signature at registration, one `Context` per trigger, values typed `Any`, a non-copyable
   manager, and the non-goals of the design page.

## 3. What differs today

**Baseline on `main`** [verified], Python 3.14.10 on macOS: `ruff check`, `ruff format --check`,
`ty check`, `lint-imports`, `inv test.doctest`, `mkdocs build --strict` and `uv build` pass, 801
unit and integration tests pass with 100% line and branch coverage (333 statements, 86 branches),
and `pytest tests/benchmarks --benchmark-disable` passes (40 tests).

No defect was found in the order, the snapshot, the `once` claim between threads or the way the
calling rule of `main` is applied (P7 to P10).

### Library

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Property | Status                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | --------------------- |
| F1  | **The reentrancy of the lock promises too much.** Its comment says that a signal handler or a finalizer that runs while it is held "can use the manager". With a signal handler that calls `reset()`, `subscription.remove()`, documented to never raise, raised `KeyError: 'e'`, and a new subscription was `active` without being registered (section 6). `repr(manager)` can raise `dictionary changed size during iteration`.                                                                                                                            | P6, P14  | [verified]            |
| F2  | **An error message is not bounded.** `PeriodicCondition(-10**4000)` raises a message of 4,047 characters (4,048 for `start`), while the architecture page says that the messages stay short whatever the size of the data. Above 4,300 digits, the `ValueError` of Python replaces it on every version, not on 3.11 and 3.12 only.                                                                                                                                                                                                                           | P12      | [verified]            |
| F3  | **Two statements about Python are wrong or missing.** (a) A handler or a condition that raises `StopIteration` gives a `RuntimeError` without note from `atrigger_event` (the note is on its `__cause__`): "propagates unchanged" has an exception that no page says. (b) The limit "`set.add` is rejected on Python 3.11 and 3.12, and accepted from 3.13" is false: the unbound `set.add` is rejected on 3.11 to 3.15, and the bound `set().add` is what changes. The unbound `dict.clear` is accepted from 3.13, and would receive the context as `self`. | P11, P19 | [verified, 3.11-3.15] |
| F4  | **The `repr` of a subscription hides why a handler does not run.** It shows the event and the handler, not `once`, the condition or `active`. The troubleshooting list asks the reader to check the condition and `active` one by one.                                                                                                                                                                                                                                                                                                                       | P16      | [reading]             |
| F5  | **Internal helpers look public.** The reference publishes the seven names of `minevent.calls`, of which `minevent` exports the type `Handler` only. No page says what is stable.                                                                                                                                                                                                                                                                                                                                                                             | P1       | [reading]             |
| F12 | **A condition shows a count that cannot be read.** The `repr` of a `PeriodicCondition` has `step`, the number of calls, next to the properties `freq` and `start`, but there is no `step` property.                                                                                                                                                                                                                                                                                                                                                          | P15      | [reading]             |
| F13 | **A signature decides between two calls.** A user cannot assume that a handler receives the context: adding or removing a default changes the call, and `def f(context=None)` is called without argument.                                                                                                                                                                                                                                                                                                                                                    | P5       | [verified]            |

### Documentation, tests and repository

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Property | Status                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------- |
| F6  | **Rules have several homes.** `once`, `atrigger_event`, the calling rule and the `with` block each appear in 5 to 7 files among the README, the pages and the docstrings. The five "Pitfalls" of the guide repeat the "Limits" and the "Registration" sections of the architecture page. The "In practice" lines of the design page and the "Recommendations" of the guide give advice twice.                                                                                               | P19      | [verified], by search  |
| F7  | **The tests of the source distribution do not pass.** It holds `tests/` but not `dev/`, and `tests/unit/test_benchmark_trend.py` imports `dev.benchmark_trend`, so the collection of `tests/unit` stops with `No module named 'dev'`. That test checks a script of the nightly benchmark, not the package. A second failure hides behind it: `sources = ["src"]` applies to the sdist too and moves `src/minevent` to `minevent`, and `test_version_fallback_without_metadata` reads `src`. | P23      | [verified]             |
| F8  | **Files and dependencies without a use.** `review/context_object_design.md` describes an API that no longer exists (`trigger_event("e", epoch=3)`, `filter_payload`). The docs dependency `mkdocs-include-markdown-plugin` is in no plugin list and no page, and the strict build passes without a use of it. The changelog describes removals of names that no release had (`__len__`, `AfterNCondition`).                                                                                 | P22      | [verified]             |
| F9  | **The layering contract is not exhaustive**: a new module that is in no layer is not checked. `exhaustive = true` passes on `main`.                                                                                                                                                                                                                                                                                                                                                         | P20      | [verified]             |
| F10 | **Tests against their own rules**: `test_calls_does_not_import_annotationlib_before_python_3_14` has three asserts, and 3 pairs of unit tests have identical bodies. `test_manager.py` has 1,725 lines and 14 sections, among them the tests of `Subscription` conveniences, `_remove` and registration.                                                                                                                                                                                    | P22      | [verified]             |
| F11 | **The header of `ci.yaml` is false**: it says that the branch protection of `main` requires three checks, and `.github/GUIDELINES.md` calls the job ids load-bearing for it. The branch protection and the ruleset have an empty list of required checks.                                                                                                                                                                                                                                   | P19      | [verified], 2026-11-26 |

What is already right and must not regress: callables as handlers and conditions; the signature
checked once, at registration; the early rejection of coroutine and generator functions; one
read-only `Context` per trigger; the atomic `once` claim; the O(1) removal; the release of handlers
outside the lock; errors that are never replaced by `minevent`; the exact counter of the condition;
100% coverage.

## 4. Architecture

```text
add_event_handler(event, handler, *, once, condition)
        |   _check_event, callable, once is a bool
        |   Subscription: calls.check_signature, calls.has_kind  -> TypeError if f(context) does not fit
        v
EventManager._subscriptions                  event -> ordered dict of Subscription, under the lock
        |   the manager alone sets Subscription._active
        v
trigger_event(event, context) / atrigger_event(event, context)
        |   snapshot under the lock, one Context (final)
        |   trigger_event only: an async handler in the snapshot -> TypeError, nothing has run
        v
for each subscription:
        removed, or guarded and not _claim(context)  -> skip   condition -> still active -> once
        handler(context)
        awaitable result                             -> TypeError (sync) or await (async)
        exception          -> note with calls.describe and calls.describe_event
```

The modules and their layers are the ones of `main`:

| Module                   | Layer | Holds                                                                             | Change        |
| ------------------------ | ----- | --------------------------------------------------------------------------------- | ------------- |
| `minevent/__init__.py`   | top   | the exports, `__version__`                                                        | none          |
| `minevent/manager.py`    | 1     | `Subscription`, `EventManager`, `_check_event`, `_as_context`                     | 4.1, 4.2, 4.7 |
| `minevent/calls.py`      | 2     | how user code is checked and named: `Handler`, `check_signature`, `describe`, ... | 4.5, 4.7      |
| `minevent/conditions.py` | 2     | `Condition`, `PeriodicCondition`                                                  | 4.3, 4.4, 4.7 |
| `minevent/context.py`    | 3     | `Context`                                                                         | none          |

### 4.1 The lock says what it protects (F1, F3)

The registry stays a dict of dicts under an `RLock`. Making every method safe against an
interruption between any two instructions needs either a copy of the registry at each change, which
loses the O(1) removal, or a protocol that is harder to read than the registry itself. The limit is
stated instead (D1), and the comment says why the lock is reentrant:

```python
# This lock protects the state above against the other threads. The handlers run without it. It is
# reentrant, so a signal handler or a finalizer that interrupts a method does not deadlock, but it
# must not change the manager: the method that it interrupts expects the state to stay.
self._lock = threading.RLock()
```

The sentences of `clear_event` and `reset` about the finalizers of the removed handlers stay: these
handlers are released when the method returns, outside the lock.

No code catches `StopIteration`: a coroutine cannot raise it, so `minevent` could only replace it by
another exception.

### 4.2 The `repr` of a subscription (F4)

The options that are not the default, and the state if the registration is gone:

```python
def __repr__(self) -> str:
    parts = [f"event={self._event!r}", f"handler={describe(self._handler)!r}"]
    if self._once:
        parts.append("once=True")
    if self._condition is not None:
        parts.append(f"condition={describe(self._condition)!r}")
    if not self._active:
        parts.append("active=False")
    return f"{self.__class__.__qualname__}({', '.join(parts)})"
```

A registered handler without options reads as today.

### 4.3 Bounded errors of the condition (F2)

The two `ValueError` of `PeriodicCondition` show the value with `reprlib.repr`, like the other
values of the library:

```python
msg = f"freq must be greater than or equal to 1, got {reprlib.repr(freq)}"
```

### 4.4 The `step` of the condition (F12)

A read-only property, next to `freq` and `start`. It does not advance the counter:

```python
@property
def step(self) -> int:
    return self._step
```

It is the number of calls since the creation or the last `reset()`, and a copy starts with the value
of the original. It reads one integer, so it needs no lock.

### 4.5 One home per rule (F5, F6)

| Page              | Its only job                                 | Change                                                                                 |
| ----------------- | -------------------------------------------- | -------------------------------------------------------------------------------------- |
| `README.md`       | what it is, one example, installation, links | the calling rule becomes one sentence and a link; the usage keeps register and trigger |
| `index.md`        | entry page of the site                       | none                                                                                   |
| `quickstart.md`   | the first contact, one example per feature   | no rule restated beside an example                                                     |
| `examples.md`     | recipes that combine features                | the recipes that repeat a quickstart section are removed or merged into it             |
| `guide.md`        | recommendations and troubleshooting          | "Pitfalls" is deleted                                                                  |
| `architecture.md` | **the rules, the guarantees and the limits** | the public API statement (P1), the limits of section 1                                 |
| `design.md`       | the reasons and the trade-offs               | "In practice" links to the guide when the guide says it                                |
| `refs/`           | the exported names                           | `refs/calls.md` shows `Handler` and `check_signature` only (the `members` option)      |

The changelog describes `0.6.0` against `0.5.0` only: the entries about names and behaviours that
existed between two releases are folded into the description of the final one.

### 4.6 Repository and tests (F7 to F11)

- **Lean**: delete `review/context_object_design.md` (git keeps it) and the unused docs dependency.
- **Layers**: `exhaustive = true` in the contract of `import-linter`.
- **Tests**: split the test of three asserts, delete the second test of each identical pair, and
  split `test_manager.py` by feature (`test_manager_registration.py`, `test_manager_context.py`,
  `test_manager_trigger.py`, next to the files for async, `once` and subscriptions).
- **CI comments**: `ci.yaml` and `GUIDELINES.md` describe the protection that exists (D6).
- **Distribution** (F7): the sdist keeps the tests and the `src/` layout, and leaves out the one
  test of `dev/`, which stays in the repository and in CI. The rewrite of the paths is a setting of
  the wheel only, so the wheel holds the same files as today:

  ```toml
  [tool.hatch.build.targets.sdist]
  only-include = ["src", "tests"]
  exclude = ["tests/unit/test_benchmark_trend.py"]

  [tool.hatch.build.targets.wheel]
  packages = ["src/minevent"]
  ```

### 4.7 One call, checked (F13)

`calls.adapt_call` returned a callable of the context. It becomes a check that returns nothing:

```python
def check_signature(func: Callable[..., object], name: str) -> None:
    # The generator check and the read of the signature are the ones of adapt_call.
    required = [param for param in signature.parameters.values() if param.default is param.empty]
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(required) != 1 or required[0].kind not in positional:
        msg = (
            f"{name} {describe(func)} must take the context as its only required argument; "
            "wrap it in a function or a lambda"
        )
        raise TypeError(msg)
```

- `Subscription` calls the handler and the condition directly: `_handler_call` and `_condition_call`
  are deleted.
- `Handler` is `Callable[[Context], object]`, and `Condition` is `Callable[[Context], bool]`.
- `PeriodicCondition.__call__` takes the context and ignores it. The parameter is named `_context`,
  which the lint accepts without a `noqa` [verified].

A handler that does not need the context declares it and ignores it. `def f(_)` is the form that the
documentation recommends; it passes `ty` and the unused argument rules of ruff [verified]:

```python
def save_model(_: Context) -> None: ...


manager.add_event_handler("epoch_end", save_model)
manager.add_event_handler("epoch_start", lambda _: model.train())  # an existing function
```

A lambda is for a function that cannot be changed. It costs two things [verified]: the notes and the
`repr` show `<lambda>`, and a coroutine function behind it is only detected after its call by
`trigger_event`, once the earlier handlers have run.

## 5. Public API after the change

The manager keeps its signatures. A handler and a condition take the context.

```text
from minevent import (
    Condition,  # Callable[[Context], bool]
    Context,  # Mapping[str, Any], final
    EventManager,
    Handler,  # Callable[[Context], object]
    PeriodicCondition,  # (freq, *, start=0)
    Subscription,  # returned by the manager
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
event in manager

subscription.event, .handler, .once, .condition, .active
subscription.remove()  # bool
with subscription: ...  # removed on exit

condition(context), condition.reset(), condition.freq, condition.start, condition.step
```

### Migration

| Before                                                              | After                                                     |
| ------------------------------------------------------------------- | --------------------------------------------------------- |
| `repr` of a `once`, conditional or removed subscription: two fields | it adds `once=True`, `condition='...'` or `active=False`  |
| the whole integer in a `ValueError` of `PeriodicCondition`          | shortened by `reprlib`                                    |
| `minevent/` at the root of the source distribution                  | `src/minevent/`, next to `tests/`                         |
| the functions of `minevent.calls` in the reference                  | `check_signature` only; the others have no stability rule |
| `calls.adapt_call`                                                  | removed                                                   |

### Migration of the handlers and the conditions

| Today                                               | After                                               |
| --------------------------------------------------- | --------------------------------------------------- |
| `def f():`                                          | `def f(_):`, or register `lambda _: f()`            |
| `add_event_handler("e", model.train)`               | `add_event_handler("e", lambda _: model.train())`   |
| `lambda: print("done")`                             | `lambda _: print("done")`                           |
| `lambda i=i: save(i)`                               | `lambda _, i=i: save(i)`                            |
| `functools.partial(save, "model.pt")`, `save(path)` | `lambda _: save("model.pt")`                        |
| `condition=lambda: flag.enabled`                    | `condition=lambda _: flag.enabled`                  |
| `lambda: all([a(), b()])`                           | `lambda context: all([a(context), b(context)])`     |
| `condition()` of a `PeriodicCondition`              | `condition(context)`                                |
| `add_event_handler("e", manager.reset)`             | `add_event_handler("e", lambda _: manager.reset())` |

## 6. Evidence

**Interrupted methods** [verified]. A loop of `add_event_handler`, a check of `active` against
`get_subscriptions` with the signal blocked, `remove()` and `repr()`, during 20 s, with a `SIGALRM`
about every 37 µs whose handler calls `reset()`. The rate is far above what a program does: it shows
that the window exists, not how often a program meets it.

| Python  | Iterations | `KeyError` from the loop (`remove`) | `active` but not registered |
| ------- | ---------: | ----------------------------------: | --------------------------: |
| 3.11.18 |  2,123,342 |                               8,113 |                       7,847 |
| 3.13.18 |  2,021,317 |                               6,452 |                       6,687 |
| 3.14.10 |  1,634,167 |                               1,592 |                       2,146 |

A `reset()` or an `add_event_handler` injected with a trace function at each line of a method also
gives the `RuntimeError` of `repr` [verified, 3.14, by injection only]. A stress with a finalizer run
by the garbage collector (300,000 iterations) showed no failure: the finalizer case is **[reading]**.

**Prototype** of 4.2 and 4.3 on a scratch copy of `main` [verified, 3.14]. `ruff check`,
`ruff format --check` and `ty check` are clean on its `src`, the doctests of `src`, the README and
the documentation pages pass, and 797 tests pass and 4 fail: the 4 tests of the `repr` of a
subscription that is built by hand, which now shows `active=False`. The message of
`PeriodicCondition(-10**4000)` has 85 characters.

**Prototype** of 4.7: section 10. It has no new docstrings, its tests are not adapted, and it was not
combined with the other prototypes.

**Source distribution** [verified, 3.14, macOS]. Built with `uv build`, installed in a new
environment with the test tools, and tested from the unpacked archive:

| Configuration            | Unit and integration tests | Benchmarks, disabled |
| ------------------------ | -------------------------- | -------------------- |
| `main`                   | collection error           | 40 pass              |
| `main` plus `dev/`       | 800 pass, 1 fails          | 40 pass              |
| the configuration of 4.6 | 789 pass                   | 40 pass              |

The second row shows the failure of the layout alone. The configuration of 4.6 runs the 801 tests of
`main` without the 12 of `test_benchmark_trend.py`. Its wheel lists the same files as on `main`, and
its archive has 56,309 bytes, against 57,267 on `main`. An editable install with the same settings of
the wheel imports `src/minevent`.

**Speed of `main`** (Python 3.14.10, µs, best of 9 repetitions) [verified]: 0.20 for a trigger
without handler, 0.31 with one, 0.88 with ten, 0.73 with one and a small dict, 5.5 for a
registration plus its removal, 0.15 for a call of a `PeriodicCondition`. They agree with P18.

**Size of `main`** [verified]: `src` has 1,499 lines, 969 of them in docstrings; the unit,
integration and benchmark tests have 5,131, 1,269 and 391 lines.

**Not verified**: the tests, the signal stress and the speed on Linux; the free-threaded builds; F1
on 3.12 and 3.15, and F2 on 3.15; the changes of 4.1 and 4.4 to 4.6, apart from the `exhaustive`
contract and the configuration of the distributions; 4.7 beyond its prototype.

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own. Each step updates the
docstrings, the documentation and the changelog for what it changes.

| Step | Branch                                       | Change                                                                                                                           | Breaking     | Fixes      |
| ---- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------ | ---------- |
| 1    | `docs/state-the-limits-of-the-manager`       | The comment of the lock, the limits on signals, `StopIteration`, async generators, signatures and huge integers (4.1, section 1) | guarantee    | F1, F3     |
| 2    | `bugfix/shorten-condition-errors`            | `reprlib` in the errors of `PeriodicCondition` (4.3)                                                                             | messages     | F2         |
| 3    | `feat/show-subscription-options`             | The `repr` of a subscription (4.2), the troubleshooting of the guide                                                             | output       | F4         |
| 4    | `chore/remove-unused-files`                  | The old proposal, the docs dependency, `exhaustive = true` (4.6)                                                                 | no           | F8, F9     |
| 5    | `bugfix/run-the-tests-of-the-sdist`          | The content and the layout of the sdist (4.6)                                                                                    | distribution | F7         |
| 6    | `test/split-manager-tests`                   | The tests (4.6)                                                                                                                  | no           | F10        |
| 7    | `ci/fix-protection-comments`                 | The comments about the branch protection (D6)                                                                                    | no           | F11        |
| 8    | `docs/give-each-rule-one-page` (on 1, 3, 10) | The pages, the reference of `calls`, the public API statement, the changelog (4.5)                                               | no           | F5, F6, F8 |
| 9    | `feat/add-condition-step`                    | The `step` property (4.4)                                                                                                        | no           | F12        |
| 10   | `feat/always-pass-the-context` (on 2, 3)     | One call, checked, with its documentation, changelog and tests (4.7)                                                             | **yes**      | F13        |

Order of value if only part is taken: **1 and 2** (a documented guarantee is false), then **3** and
**10** (the largest breaking change, best made before a release), then **5** (a release that cannot
be tested), **8** (the largest maintenance gain) and the others. Release `0.6.0` after the steps 1 to
3, 5 and 8 to 10, with `SECURITY.md` set to `0.6.x` and its generic advice reduced to what concerns
`minevent`.

## 8. Tests and gates

Unit tests mirror the source tree; the rules of `CLAUDE.md` apply (one behaviour per test, `match` on
every `pytest.raises`, literals for expected values, a regression test that fails on `main`).

| Test                                                                   | Behaviour                                          | Step |
| ---------------------------------------------------------------------- | -------------------------------------------------- | ---- |
| `test_event_manager_atrigger_event_stop_iteration`                     | `RuntimeError`, as documented                      | 1    |
| `test_atrigger_event_stop_iteration_has_the_noted_cause` (integration) | the `__cause__` has the note                       | 1    |
| `test_periodic_condition_huge_negative_freq` and `..._start`           | the whole message as one literal (fails on `main`) | 2    |
| `test_subscription_repr_options` (parametrized)                        | `once`, condition, both, removed: one literal each | 3    |
| `test_subscription_repr_registered`                                    | no extra field for a registration without options  | 3    |
| `test_subscription_repr_condition_ignores_repr`                        | a condition whose `repr` raises is named           | 3    |
| `test_periodic_condition_step` (parametrized)                          | 0 at creation, then the number of calls            | 9    |
| `test_periodic_condition_step_reset`                                   | 0 after `reset()`                                  | 9    |
| `test_periodic_condition_step_does_not_advance`                        | a read leaves the next result unchanged            | 9    |
| `test_check_signature_accepted` (parametrized)                         | `f(context)`, `f(_)`, one more default, a partial  | 10   |
| `test_check_signature_rejected` (parametrized)                         | no parameter, only defaults, `*args`, two, keyword | 10   |
| `test_periodic_condition_call_with_context`                            | the context changes no result                      | 10   |
| `test_type_checker_reports_a_wrong_handler` (integration, new cases)   | `ty` reports a function without parameter          | 10   |

No test asserts the behaviour under a signal (F1): it is a limit, and a test of it would depend on
timing.

Gates before each merge: `ruff check src tests`, `ruff format src tests`, `ty check`,
`lint-imports`, `pytest tests/unit tests/integration --cov=minevent --cov-branch` at 100%,
`inv test.doctest`, `mkdocs build --strict -f docs/mkdocs.yml` and `python tests/package_checks.py`.
Step 5 is checked with `uv build`, the tests run from the unpacked sdist and the list of the files
of the wheel. Step 6 compares the list of the collected tests before and after: only the removed
duplicates and the split test differ.

## 9. Decisions for the maintainers

- **D1. Support a signal handler that changes the manager?** _Recommended: no, state the limit._ The
  safe pattern (set a flag) is the usual one for signals. Alternative: replace the dicts by immutable
  tuples swapped under the lock. It removes the `RuntimeError` but not a lost update between a read
  and a swap, and a removal becomes O(n). A plain `Lock` is worse: it deadlocks.
- **D2. Replace the calling rule by one shape, `f(context)`?** _Decided: yes, checked at
  registration_ (4.7). A user can assume that there is always an input context. `model.train` is no
  longer registered as it is. Compared in section 10.
- **D3. Show the options in the `repr` of a subscription?** _Recommended: yes_ (about 8 lines).
  Alternative: keep the short form and the troubleshooting steps.
- **D4. Ship the tests in the sdist?** _Decided: yes_, without `dev/`, and not in the wheel.
  Downstream packagers, such as Linux distributions and conda-forge, and offline users build from the
  sdist and run its tests. The test of `dev/benchmark_trend.py` is left out of the sdist. Alternative:
  skip it in the test file when `dev` is missing, which adds a condition to a test.
- **D5. Remove `ci-cyclic-imports.yaml`?** _Decided: no._ It has another purpose than the layers
  contract: it verifies the package itself, from the imports of its source, while the contract checks
  declared rules, which can be outdated and miss a cycle.
- **D6. Require the checks that `ci.yaml` names, or fix the comment?** _Recommended: fix the
  comment._ When read, the last 60 runs of `ci.yaml` (2026-11-26) held 1 success, 46 cancelled, 12
  queued and 1 pending [verified]: a required check would block merges while the queue is that long.
  Requiring the three checks later needs no new job.
- **D7. Remove `on` or `in`, which duplicate another way?** _Recommended: no._ `on` returns the
  function and `add_event_handler` the subscription; `in` is O(1), while `events` copies the names.
- **D8. `_check_event` is a validator of one `isinstance`, which `CLAUDE.md` forbids.**
  _Recommended: keep it and let the rule allow a validator that several functions share._ Four
  functions use it. Alternative: write the check four times.
- **D9. Give `PeriodicCondition` a `step` property?** _Decided: yes_ (4.4).
- **D10. Test the sdist in CI?** _Decided: later._ Tracked in #910. Until then, P23 is checked by
  hand.

## 10. D2: why one call, checked

The comparison behind the decision. On `main`, a handler or a condition is called as `f()` or
`f(context)`, and its signature decides which. The alternative is one call, `f(context)`, in two
variants, which differ in what happens to a callable that does not fit:

- **Today** (`main`): `f()` if no parameter lacks a default, `f(context)` if exactly one positional
  parameter does, otherwise `TypeError` at registration.
- **A. One call, checked** (chosen): always `f(context)`. A callable is accepted if exactly one
  parameter lacks a default and it is positional; otherwise `TypeError` at registration. It is
  today's rule without its `f()` branch.
- **B. One call, unchecked**: always `f(context)`. The signature is not read; Python raises at the
  trigger if the call does not fit. Generator and coroutine functions are still detected.

In both variants `Handler` is `Callable[[Context], object]`, `Condition` is
`Callable[[Context], bool]`, and `PeriodicCondition` is called as `condition(context)`.

### What a registration does

[verified, 3.14, prototypes of A and B on a scratch copy of `main`]

| Callable                         | Today             | A: checked        | B: unchecked                        |
| -------------------------------- | ----------------- | ----------------- | ----------------------------------- |
| `def f(context)`                 | gets the context  | gets the context  | gets the context                    |
| `def f(context, verbose=False)`  | gets the context  | gets the context  | gets the context                    |
| `partial(save, "model.pt")`      | gets the context  | gets the context  | gets the context                    |
| `Model.save`, unbound            | context as `self` | context as `self` | context as `self`                   |
| `def f()`                        | `f()`             | rejected          | `TypeError` at the trigger          |
| `model.train(mode=True)`         | `model.train()`   | rejected          | **`model.train(context)`**          |
| `lambda i=i: ...`                | keeps `i`         | rejected          | **`i` is the context**              |
| `def f(context=None)`            | **gets `None`**   | rejected          | gets the context                    |
| `print`                          | rejected          | rejected          | prints the context                  |
| `Mock()`                         | rejected          | rejected          | gets the context                    |
| `max`                            | rejected          | rejected          | **runs on the keys of the context** |
| `def f(a, b)`, `def f(*, epoch)` | rejected          | rejected          | `TypeError` at the trigger          |

Bold cells run without an error and probably not as the author meant. **B does not drop the support
of `model.train`: it calls it with the context as `mode`.**

### Cost

| Measure [verified, 3.14, macOS]                            | Today |       A |      B |
| ---------------------------------------------------------- | ----: | ------: | -----: |
| code lines of `src`, without docstrings and comments       |   404 |     402 |    384 |
| trigger with 1 handler that takes the context, µs          |  0.29 |    0.29 |   0.29 |
| trigger with 10 such handlers, µs                          |  0.71 |    0.71 |   0.71 |
| trigger with 10 handlers without argument today, µs        |  0.89 |     n/a |    n/a |
| registration plus removal, µs                              |   6.3 |     6.3 |    2.3 |
| unit and integration tests of `main` that fail             |     0 |     350 |    190 |
| tests not collected (`test_calls.py` imports `adapt_call`) |     0 |     135 |    135 |
| failing doctest examples, README and pages / `src`         | 0 / 0 | 68 / 18 | 27 / 5 |

The tests and the examples were not adapted: the counts show the size of the migration, mostly the
handlers without parameter. B fails fewer of them partly because a wrong registration that is never
triggered passes [reading].

With the types of A, which B shares, `ty check` reports `def f()`, `model.train`, `lambda: None`
and `def f(a, b)` in a sample (today: `def f(a, b)` only) [verified]. It does not report
`def f(context=None)`, `lambda i=3: None` or `print`.

### Pros and cons

| Approach         | Pros                                                                                                                                                                                                                                                                                              | Cons                                                                                                                                                                                                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Today**        | `model.train`, `lambda: ...` and functions without parameter are registered as they are. No change for users or tests.                                                                                                                                                                            | Two call shapes to learn, chosen implicitly. Adding or removing a default changes the call. `def f(context=None)` silently gets `None`. A table of 11 rows documents the rule.                                                                                                                                                                     |
| **A: checked**   | **One call to learn.** An accepted callable behaves as today, and a callable that no longer fits is rejected at registration, so no migration is silent. The footgun of the optional parameter becomes an error. A wrong signature is still found before the first trigger. No cost on a trigger. | A function without parameter needs one (`def f(context)`) or a lambda. A function that calls a `PeriodicCondition` without argument raises at the trigger. `def f(context: Context \| None = None)` is rejected. The signature inspection, the `annotationlib` branch and the differences between Python versions stay: almost no code is removed. |
| **B: unchecked** | One call to learn, and the simplest rule: what Python accepts runs. About 20 code lines, `adapt_call` and `annotationlib` go. A registration is 4 µs faster. `print`, `Mock()` and any `*args` callable work. No difference between Python versions.                                              | **A callable with an optional first parameter receives the context silently**, including code that works today. A wrong signature raises at the trigger, perhaps hours into a training, after the earlier handlers ran, and consumes a `once` registration. It gives up "validated at the door" (P4) for signatures.                               |

### Why A

It gives what motivates the change, a context that is always there, without a silent change of
behaviour: the one call that is not checked at registration, `condition()` inside a function of the
user, raises. B is the real simplification of the code, but it saves only 20 code lines of the 404,
next to what it costs: calls that succeed with the wrong argument.

## 11. Not covered

- **The non-goals of the design page** (event objects, priorities, wildcards, weak references,
  collected errors, concurrent dispatch): unchanged.
- **The name of the event in the `Context`**, for a handler registered to several events: bind it with
  `functools.partial`.
- **Return values of handlers** and **typed payloads**: need their own design if users ask.
- **A helper that ignores the context**, such as `ignore_context(model.train)`: a lambda does it.
  It could keep the name and the detection of a coroutine, so revisit it if users wrap often.
- **The nightly benchmark**: whether its 50% threshold is a usable signal on the shared runners, and
  whether `dev/benchmark_trend.py` is worth its upkeep. No scheduled run of `main` with the current
  baseline (#878) had been read.
- **The `bot-`, `release-` and `security-` workflows and the `.make/` subtree**: not reviewed.

---

## Appendix: effect on the size of the package

| Item                   | Today | Target | Why                                    |
| ---------------------- | ----: | -----: | -------------------------------------- |
| exported names         |     7 |      7 | six names and `__version__`            |
| modules                |     5 |      5 | no change                              |
| runtime dependencies   |     0 |      0 |                                        |
| `src` lines            | 1,499 |    n/a | not measured with the final docstrings |
| documents in `review/` |     2 |      1 | the old proposal is deleted            |

The prototype of 4.2 and 4.3 adds 11 lines and removes 6. Without docstrings and comments, the one of
4.7 removes 2 of the 404 lines of `main`. The gate is the behaviour (sections 1 and 8), not the size.
