# `minevent`: target state and the changes to reach it

This document describes the design that `minevent` should have, then the changes to make to the
current implementation (`main`, `ebbee93`, #927) to get there. The design follows the properties of
the "How It Works" page (`docs/docs/architecture.md`), the reasons of the "Design Choices" page
(`docs/docs/design.md`) and the rules of `CLAUDE.md`. It replaces the previous version, whose plan
was merged (#911 to #921) except the release of `0.6.0`.

The conclusion first: **the design of the library is the target.** The review found no defect in the
registration, the dispatch, the payload or the conditions, and recommends **no change of behaviour
or of the exported names**. Breaking changes were allowed, and the candidates were compared
(section 9): each one costs more than the problem it solves. What is left is at the edges: guides
that lead a user into a trap, rules written twice, documentation links and a distribution that no
check covers, a script without a test, and a release that has not happened.

The aim in one line: **ship what is on `main`, with documentation that a user can copy and gates
that keep it true.**

Items are tagged **[verified]** (reproduced on 2026-11-26 with a script, a test run, a build or a
read of the GitHub API, on an Apple laptop; scripts kept outside the repository) or **[reading]**
(from the code, the documents or the workflows). This change touches this document only: nothing in
`src`, `tests`, `dev`, `docs` or `.github` is modified.

---

## 1. Properties of the sub-package

The package is three concepts (_event_, _handler_, _manager_), the `Subscription` that a
registration returns, the read-only `Context` of a trigger, and the plain-callable _conditions_.
These are the rules of the target. Each design choice below exists to make one of them true by
construction, or to say exactly where it stops. "Status" compares the row with `main`: **holds**
(true today) or **gap** (see the finding of section 3).

### Surface and registration

| #   | Property              | Statement                                                                                                                                                                                                                                                                                                                                                                                  | Enforced by                           | Status |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- | ------ |
| P1  | Small surface         | Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Handler`, `Condition`, `PeriodicCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `in`. The public API is what `minevent` exports, and the reference shows it and nothing else. | `__all__`, the reference page         | gap F6 |
| P2  | Standard library only | No runtime dependency. `import minevent` starts no thread, emits no warning and writes no output and no log. Plain imports at the top of the modules.                                                                                                                                                                                                                                      | `package_checks.py`, `test_import.py` | holds  |
| P3  | Events are strings    | An event name is a case-sensitive `str` (a `StrEnum` member is one). The methods of the manager raise `TypeError` for another type, and `in` answers like a dict. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                   | `_check_event`                        | holds  |
| P4  | Validated at the door | `add_event_handler` checks every argument: `TypeError` for a wrong type, `ValueError` for a wrong value. `once` is a `bool`, and the integers of a condition are an `int` but not a `bool`. A rejection leaves the manager as it was.                                                                                                                                                      | `add_event_handler`, `calls`          | holds  |
| P5  | One call              | A handler and a condition are always called as `f(context)`. Exactly one parameter lacks a default, and it is positional. Anything else is rejected at registration. The signature is read once. Names and annotations are not checked.                                                                                                                                                    | `calls.check_signature`               | holds  |

### Dispatch

| #   | Property               | Statement                                                                                                                                                                                                                                                                          | Enforced by                         | Status |
| --- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ------ |
| P6  | Registration identity  | `add_event_handler` returns a new `Subscription` every time. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` exactly while the registration is in the manager. It cannot be copied or pickled.                                  | `Subscription`, `EventManager`      | holds  |
| P7  | Order                  | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                        | the ordered `dict`                  | holds  |
| P8  | Snapshot, removal wins | A trigger visits the registrations that exist when it starts. An addition waits for the next trigger. A registration removed before its handler is called does not run, whoever removed it.                                                                                        | `Subscription._claim`               | holds  |
| P9  | `once` is at-most-once | A `once` registration is removed by an atomic claim after its condition and just before its handler. A false or raising condition does not consume it; a handler that raises does.                                                                                                 | `Subscription._claim`               | holds  |
| P10 | No silent drop         | The return value of a handler is ignored, unless it is awaitable: `atrigger_event` awaits it, one handler at a time, and `trigger_event` raises `TypeError`. A coroutine function in the snapshot is rejected by `trigger_event` before anything runs. Conditions are synchronous. | `trigger_event`, `reject_awaitable` | holds  |

### Errors, payload, threads

| #   | Property                | Statement                                                                                                                                                                                                             | Enforced by                        | Status |
| --- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ------ |
| P11 | Fail-fast, never masked | An exception of a handler or a condition propagates unchanged, with a note that names the event and what raised, and the next handlers are skipped. Adding the note never raises instead of it.                       | `calls.add_error_note`, `describe` | holds  |
| P12 | Bounded messages        | A message or a note of `minevent` is short whatever the size of the user data: values are shown with `reprlib`, an event name is shortened above 200 characters, and a missing key lists at most 20 keys.             | `reprlib`, `calls.describe_event`  | holds  |
| P13 | Payload is data         | One read-only `Context` per trigger, shared by the handlers and the conditions, from a mapping with `str` keys or a `Context` used as is. The keys that are checked are the keys that are stored. `Context` is final. | `Context`, `typing.final`          | holds  |
| P14 | Thread-safe registry    | The registry is protected by a lock against the other threads, with and without the GIL. Handlers, conditions and the finalizers of the removed handlers run outside it.                                              | `EventManager._lock`               | holds  |
| P15 | Exact condition         | `PeriodicCondition` counts every call once, from any number of threads, can be copied and pickled, and shows its count in `step`.                                                                                     | the counter lock                   | holds  |
| P16 | Explicit, no state      | No global manager, no discovery, no side effect of a read, no log. A manager is always truthy, has no length, and cannot be copied or pickled. The `repr` of a subscription shows what decides whether it runs.       | `__reduce__`, `__repr__`           | holds  |

### Engineering

| #   | Property          | Statement                                                                                                                                                                                | Enforced by                  | Status         |
| --- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | -------------- |
| P17 | Typed             | Fully typed, `py.typed`, `ty` and `pyright` clean. A type checker reports a handler or a condition without parameter, and an asynchronous condition.                                     | `inv types.check --complete` | holds          |
| P18 | Fast and linear   | About 0.3 µs for a trigger with one trivial handler, 0.05 µs for each extra one, 0.8 µs with a small dict, 6 µs for a registration plus its removal. A removal is O(1).                  | `tests/benchmarks/`          | holds          |
| P19 | Copyable docs     | An example or a recommendation of the documentation works as written, and does what its sentence says.                                                                                   | doctests, review             | gap F1 to F4   |
| P20 | One home per rule | A rule of the library is stated by one documentation page. The behaviour of one object is stated by its docstring. The others link to it.                                                | review                       | gap F5, F6, F9 |
| P21 | Checked docs      | A broken link or anchor between the pages fails the build.                                                                                                                               | `mkdocs.yml`                 | gap F7         |
| P22 | Layered           | `manager` imports `conditions` and `calls`, which import `context`. The two middle modules do not import each other. A new module must be placed in a layer.                             | `lint-imports`, exhaustive   | holds          |
| P23 | Tested systems    | The tests run on Linux and macOS and on every supported Python, free-threaded builds included. Windows is not supported.                                                                 | `ci.yaml`                    | holds          |
| P24 | Testable release  | The source distribution holds the tests of the package, in the layout of the repository, and they pass from it. A pull request that breaks this fails. The wheel holds the package only. | `pyproject.toml`, `ci-build` | gap F10        |
| P25 | Lean to maintain  | Every file and every dependency of the repository serves a property of this table or the layout shared with `coola`, and every script has tests.                                         | review, `pyproject.toml`     | gap F11        |
| P26 | Released          | The latest release has the API that the documentation of `main` describes, or the gap is short.                                                                                          | `release-pypi.yaml`          | gap F12        |

Not guaranteed, and documented as such (the "Limits" of the architecture page; **new** marks an item
to add):

- **A removal in another thread** cannot stop a handler whose trigger has already passed the check.
- **A signal handler or a garbage collection finalizer** must not change the manager that it
  interrupts.
- **Concurrent calls.** A registration without `once` is called by every thread that triggers its
  event. The state of a user handler or condition is its own concern.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **`StopIteration` in `atrigger_event`** becomes a `RuntimeError`.
- **The start of a coroutine.** `atrigger_event` reads the registrations and the payload when its
  coroutine starts to run.
- **Hidden coroutines and generators** are not detected at registration. A hidden coroutine is
  rejected after its call by `trigger_event`; a hidden generator does nothing.
- **A background task returned by a handler** is an awaitable like any other: `trigger_event` raises
  after the task is scheduled, and `atrigger_event` waits for it. (**new**, F1)
- **Names are not checked**, and a signature of the standard library can depend on Python.
- **A condition is evaluated by truthiness**, and it counts its calls, not the triggers. Its count
  starts at 0 in a new process unless the condition is saved and restored. (**new**, F4)
- **A cached function** cannot be a handler: a `Context` is not hashable.
- **A mutable value of the payload** can be mutated by a handler.
- **A huge integer** in a message raises the `ValueError` of Python on 3.11 and 3.12.
- **Delayed release.** A manager with registrations is in a reference cycle.

## 2. Constraints on the target

1. **Simple and easy to maintain.** No new concept. A change that costs more code or text than the
   problem it solves is rejected.
2. **Breaking changes are fine.** The latest tag is `v0.5.0` and `main` is `0.6.0a0`. No alias and no
   deprecation period. The future state matters more than the past one.
3. **Standard library only** (P2).
4. **A trigger does not get slower** (P18).
5. **Decisions of the maintainer stay**: one call, checked; Linux and macOS only; `int` only for the
   integer arguments; no `workflow-config.json`; no aggregate `ci` job; benchmarks nightly only;
   plain imports, with `TYPE_CHECKING` from `typing`; the tests in the source distribution but not
   in the wheel; and the check of the cyclic imports.
6. **Settled designs without a defect stay**: sequential async, fail-fast, the snapshot, the check of
   the signature at registration, one `Context` per trigger, values typed `Any`, a non-copyable
   manager, and the non-goals of the design page.

## 3. What differs today

**Baseline on `main`** [verified], Python 3.14.10 on macOS: `ruff check`, `ruff format --check`,
`ty check`, `pyright`, `lint-imports`, `inv test.doctest`, `mkdocs build --strict` and `uv build`
pass, and 820 unit and integration tests pass with 100% line and branch coverage (345 statements,
94 branches).

No defect was found in the library (P3 to P16).

| #   | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Property | Status                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | --------------------------------------- |
| F1  | **The advice about background work is a trap.** The design page says to "start the tasks or threads inside a handler". A short handler that returns its task, such as `lambda _: loop.create_task(upload())`, makes `trigger_event` raise "returned an awaitable; use atrigger_event" after the task is scheduled. `atrigger_event`, the advised fix, awaits the task, so the work is not in the background any more. No page says to return nothing, and no example starts a task. | P19      | [verified]                              |
| F2  | **A claim that the calling rule made false.** The design page says that "any function, method, lambda, `functools.partial` or callable object works". `model.train`, `print` and a function without parameter are rejected, as the next section of the same page says.                                                                                                                                                                                                              | P19      | [verified]                              |
| F3  | **A recipe fails for a method.** "Register a handler only once" compares with `s.handler is hello_handler`. A bound method is a new object at each access, so the same recipe with `plugin.on_epoch_end` registers it twice.                                                                                                                                                                                                                                                        | P19      | [verified]                              |
| F4  | **A resumed training is not covered.** `PeriodicCondition` counts its calls, so after a restart from epoch 7 it counts from 0, not from the epoch. The limit says that it counts calls, but no recipe gives the two ways out: a condition on the payload, or saving the condition with the checkpoint (it can be pickled).                                                                                                                                                          | P19      | [reading]                               |
| F5  | **Rules still have two homes.** The calling rule is stated in full by the architecture page and by the docstring of `check_signature`. The copy, the `step` and the `repr` of `PeriodicCondition`, the `repr` of a `Subscription` and the limit of 20 keys are each stated by a docstring and by a bullet of the architecture page.                                                                                                                                                 | P20      | [verified], by search                   |
| F6  | **The reference renders each object twice**: once on "Main classes and functions" (`::: minevent`) and once on one of four module pages. The module pages publish `minevent.calls.check_signature`, which the library says is not public.                                                                                                                                                                                                                                           | P1, P20  | [verified], on the built site           |
| F7  | **A broken anchor passes.** `mkdocs build --strict` of a copy with a link to `guide.md#no-such-anchor` succeeds: MkDocs reports it at the `INFO` level. The CI builds with `mike`, without `--strict`, so it does not fail on a warning either. The rule "one home" makes the pages depend on these anchors.                                                                                                                                                                        | P21      | [verified] (build), [reading] (CI)      |
| F8  | **Small errors.** The user guide asks for event names "in the past tense" and gives `epoch_end`. `CONTRIBUTING.md` lints `src tests` (the rule is `src tests dev`) and does not name `lint-imports`.                                                                                                                                                                                                                                                                                | P19, P20 | [reading]                               |
| F9  | **The code breaks a written rule.** `CLAUDE.md` forbids a validator of one `isinstance`. `_check_event` is one, used by four callers, and it is the right code.                                                                                                                                                                                                                                                                                                                     | P20      | [reading]                               |
| F10 | **Nothing runs the tests of the source distribution** (#910). They pass today (808 tests from the unpacked archive), but a pull request can break them without a failure: they were broken until #915.                                                                                                                                                                                                                                                                              | P24      | [verified]                              |
| F11 | **A script without a test.** `dev/generate_versions.py` (#924) has no test, which `CLAUDE.md` requires, and a weekly workflow (#927) runs it. Its output, `dev/config/package_versions.json`, is `{}` while `minevent` has no dependency.                                                                                                                                                                                                                                           | P25      | [reading], [verified] (output)          |
| F12 | **Not released.** The last tag is `v0.5.0`, whose API is not the one of `main`: `pip install minevent` gives a library that the documentation of `main` does not describe. `SECURITY.md` supports `0.5.x` only.                                                                                                                                                                                                                                                                     | P26      | [verified] (tags), [reading] (the rest) |

What is already right and must not regress: callables as handlers and conditions; the signature
checked once, at registration; the early rejection of coroutine and generator functions; one
read-only `Context` per trigger; the atomic `once` claim; the O(1) removal; the release of handlers
outside the lock; errors that are never replaced by `minevent`; the exact counter of the condition;
100% coverage.

## 4. Architecture

The library keeps its design.

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

| Module                   | Layer | Holds                                                                             | Change     |
| ------------------------ | ----- | --------------------------------------------------------------------------------- | ---------- |
| `minevent/__init__.py`   | top   | the exports, `__version__`                                                        | none       |
| `minevent/manager.py`    | 1     | `Subscription`, `EventManager`, `_check_event`, `_as_context`                     | docstrings |
| `minevent/calls.py`      | 2     | how user code is checked and named: `Handler`, `check_signature`, `describe`, ... | docstrings |
| `minevent/conditions.py` | 2     | `Condition`, `PeriodicCondition`                                                  | docstrings |
| `minevent/context.py`    | 3     | `Context`                                                                         | none       |

The code is small (413 lines without docstrings, comments and blank lines, in 1,546), the layers
are checked, and no module has a second job. Merging or splitting modules would move code without
removing any.

### 4.1 Background work from a handler (F1)

One rule, already true (P10), stated where a user meets it: **a handler that starts background work
returns nothing.** The manager cannot tell a task that the user wants to keep running from a
coroutine that was forgotten, so it does not guess (D1). The recipe, in the examples page, replaces
no code:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def upload(path: str) -> None:
...     await asyncio.sleep(0)
...     print(f"uploaded {path}")
>>> tasks = set()  # asyncio keeps a weak reference to a task only
>>> def start_upload(context: Context) -> None:
...     task = asyncio.get_running_loop().create_task(upload(context["path"]))
...     tasks.add(task)
...     task.add_done_callback(tasks.discard)
>>> manager = EventManager()
>>> _ = manager.add_event_handler("checkpoint_saved", start_upload)
>>> async def main() -> None:
...     manager.trigger_event("checkpoint_saved", {"path": "model.pt"})
...     print("training continues")
...     await asyncio.gather(*tasks)
>>> asyncio.run(main())
training continues
uploaded model.pt

```

The limits of the architecture page get one bullet, the row "Concurrent or background dispatch" of
the design page links to the recipe, and so does the troubleshooting of "returned an awaitable".

### 4.2 Examples that work as written (F2, F3, F4, F8)

| Page              | Change                                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `design.md`       | "any function, method, lambda, ... that takes the context works", with the link to the calling rule                                        |
| `examples.md`     | "Register a handler only once" compares with `==`, and its example registers a bound method                                                |
| `examples.md`     | new recipe "Resume a training": `condition=lambda context: context["epoch"] % 3 == 0`, or save the `PeriodicCondition` with the checkpoint |
| `guide.md`        | event names "after what happens": `epoch_end`, `checkpoint_saved`                                                                          |
| `CONTRIBUTING.md` | `ruff check src tests dev`, `ruff format src tests dev` and `lint-imports`                                                                 |

### 4.3 One home per rule (F5, F9)

The line between a page and a docstring follows what the rule is about:

| Rule                                          | Home                             | The other place becomes                                  |
| --------------------------------------------- | -------------------------------- | -------------------------------------------------------- |
| the calling rule (it binds the whole library) | `architecture.md`                | `check_signature`: one sentence, the link, its `Raises:` |
| the copy, `step` and `repr` of the condition  | docstring of `PeriodicCondition` | the "Threads" bullet keeps the thread safety only        |
| the `repr` of a subscription                  | docstring of `Subscription`      | the bullet of the architecture page is deleted           |
| the keys listed by a `KeyError`               | docstring of `Context`           | the "Errors" bullet keeps "the messages stay short"      |

The "Performance" bullet of the architecture page drops the number of keys too. The docstrings that
point to `check_signature` for the rule (`add_event_handler`, the module of `conditions`) point to
the page.

`CLAUDE.md` gets the exception that the code already uses (D7):

```markdown
Do not add a validator that is one `isinstance` or one comparison, unless several functions share
it. The message of a `TypeError` can name the type of the value instead of the value.
```

### 4.4 One reference page (F6)

Delete `refs/manager.md`, `refs/conditions.md`, `refs/context.md` and `refs/calls.md`, and their
lines in the navigation of `mkdocs.yml`. `refs/index.md` keeps `::: minevent`: it renders the
exported names, `Handler` included, and nothing else, so the reference and the public API (P1)
cannot differ. A copy of `docs` with this change and the one of 4.5 builds [verified].

### 4.5 A build that checks the links (F7)

In `docs/mkdocs.yml`, so the local build, the pull requests (`mike deploy`) and the releases follow
the same rule:

```yaml
strict: true
validation:
  anchors: warn
```

The pages of `main` pass with this setting, and the broken anchor of F7 aborts the build
[verified, MkDocs 1.6.1, `mkdocs build`; the effect on `mike deploy` is [reading] and is checked by
step 4].

### 4.6 Test the source distribution in CI (F10)

One step in the build job of `ci-build.yaml`, for the `sdist` cells, with no new job and no
hardcoded Python version or package name:

```yaml
- name: Test the source distribution
  if: matrix.dist-type == 'sdist'
  run: |
    set -euo pipefail
    uv build --sdist --out-dir "$RUNNER_TEMP/dist"
    mkdir "$RUNNER_TEMP/sdist"
    tar -xzf "$RUNNER_TEMP"/dist/*.tar.gz -C "$RUNNER_TEMP/sdist" --strip-components=1
    cd "$RUNNER_TEMP/sdist"
    uv venv "$RUNNER_TEMP/sdist-venv"
    VIRTUAL_ENV="$RUNNER_TEMP/sdist-venv" uv pip install . anyio pytest pytest-timeout ty
    "$RUNNER_TEMP/sdist-venv/bin/python" -m pytest tests/unit tests/integration
```

The same commands, run by hand, give 808 passed tests: the 820 of the repository without the 12 of
the script of `dev/` [verified, 3.14, macOS; the step itself was not run in CI].

### 4.7 Test the package versions script (F11)

The script, its file, its workflow and the `feu[all]` dependency stay: they are part of the layout
shared with `coola` (D6). The script gets what `CLAUDE.md` asks of every script:

- unit tests of `fetch_package_versions` and `main` in `tests/unit/test_generate_versions.py`, with
  the fetch functions of `feu` patched, so no test uses the network;
- an integration test in `tests/integration/test_generate_versions.py` that runs the real
  `fetch_package_versions` on a `pyproject.toml` without dependency, which makes no request;
- both files in the `exclude` list of the source distribution, which does not ship `dev/`.

The real function, run on the repository with the network blocked, returns `{}` [verified].

### 4.8 Release `0.6.0` (F12)

After the steps that change what is shipped or documented: the version of `pyproject.toml` (and
`uv.lock`), the heading of the changelog, the version table of the README, `SECURITY.md` set to
`0.6.x` with its generic advice reduced to what concerns `minevent`, then the tag `v0.6.0`, which
publishes. The `Changelog` URL of `pyproject.toml` can point to `CHANGELOG.md`, which holds the
migration.

## 5. Public API

Unchanged:

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

**Migration** from `main`: no code changes. The URLs of the four module pages of the reference
disappear from the new versions of the documentation. Migration from `0.5.0`: see the changelog.

**Dependents**: none in this repository.

## 6. Evidence

All [verified], 2026-11-26, macOS, on `ebbee93`.

**Tests per interpreter**, unit and integration tests against the built wheel (the repository
environment for 3.14):

| Python          | Passed | Skipped |
| --------------- | -----: | ------: |
| 3.11.18         |    813 |       7 |
| 3.12.16         |    815 |       5 |
| 3.13.18         |    815 |       5 |
| 3.14.10         |    820 |       0 |
| 3.14.10, no GIL |    820 |       0 |
| 3.15.2          |    820 |       0 |
| 3.15.2, no GIL  |    820 |       0 |

The benchmarks, run once without measure on 3.14, pass (40 tests).

**Behaviour probes** (3.14; the calling rule on 3.11 to 3.15):

| Probe                                                                             | Result                                                                     |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `print`, `max`, `dict.update`, `Mock()`, `AsyncMock()`; `set().add`, `time.sleep` | rejected; the last two on 3.11 and 3.12 only                               |
| `trigger_event`, handler that returns a task                                      | `TypeError`, the task is already scheduled                                 |
| `atrigger_event`, the same handler                                                | the task is done when the trigger returns                                  |
| condition that returns `None`                                                     | the handler is skipped, without error                                      |
| two concurrent `atrigger_event` on a `once` registration                          | one call                                                                   |
| `trigger_event` rejected for a coroutine handler                                  | the `step` of its condition stays 0                                        |
| signature whose reading raises (`__signature__`, an annotation `1/0`)             | the exception of the user code propagates unchanged, the manager unchanged |

**Types**: on a sample of user code, `ty` and `pyright` report the same two errors (a handler
without parameter, an asynchronous condition) and accept the partial, the lambda, the decorator, the
`PeriodicCondition` and a `dict[str, int]` payload. Both report a condition typed to return `None`.

**Speed** (Python 3.14.10, µs, best of 9 repetitions): 0.20 for a trigger without handler, 0.29
with one, 0.71 with ten, 4.9 with a hundred, 0.77 with one and a small dict, 6.2 for a
registration plus its removal, 0.16 for a call of a `PeriodicCondition`.

**Size**: `src` has 1,546 lines, 1,004 of them in docstrings; the unit, integration and benchmark
tests have 5,322, 1,312 and 390 lines.

**Not verified**: Linux; the stress of a signal handler of the previous review (not run again); the
changes of section 4 in CI; the recipe of 4.2 for a resumed training (not written yet).

## 7. Changes to reach the target state

One branch and one pull request per step (`CLAUDE.md`), each green on its own, each with its
changelog entry when it changes what a user or a developer sees.

| Step | Branch                                | Change                                                                    | Breaking  | Fixes     |
| ---- | ------------------------------------- | ------------------------------------------------------------------------- | --------- | --------- |
| 1    | `docs/fix-misleading-examples`        | The background recipe and limit (4.1), the corrections (4.2)              | no        | F1-F4, F8 |
| 2    | `docs/state-each-rule-once` (on 1)    | The docstrings, the bullets of the architecture page, `CLAUDE.md` (4.3)   | no        | F5, F9    |
| 3    | `docs/keep-one-reference-page` (on 2) | One reference page (4.4)                                                  | site URLs | F6        |
| 4    | `ci/check-the-documentation-links`    | `strict` and `anchors` in `mkdocs.yml` (4.5)                              | no        | F7        |
| 5    | `ci/test-the-sdist`                   | The step of `ci-build.yaml` (4.6), `.github/GUIDELINES.md`; closes #910   | no        | F10       |
| 6    | `test/generate-versions` (on 5)       | The tests of the script and the `exclude` list of the sdist (4.7)         | no        | F11       |
| 7    | `chore/release-0.6.0` (after 1-3)     | The version, the changelog, `SECURITY.md`, the README, then the tag (4.8) | release   | F12       |

Order of value if only part is taken: **1** (a user copies these pages), then **7** (nothing on
`main` reaches a user until it is released), **4** and **5** (cheap gates), then **2**, **3** and
**6**. The release waits for the steps 1 to 3 only, which change the documentation that it
publishes, and can be made without 2 and 3 if they are not taken.

## 8. Tests and gates

No step changes the behaviour of `src`, so no unit test of the library is added. Each step proves its
change:

| Step | Check                                                                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | The new examples are `pycon` blocks, run by `inv test.doctest`. An integration test starts a task from a handler with both triggers, without patching. |
| 2    | `inv test.doctest`; a search finds each rule of the table of 4.3 in its home only.                                                                     |
| 3    | The strict build; the reference page lists the six names.                                                                                              |
| 4    | A temporary broken anchor, pushed to the branch, fails the documentation job; it is removed before the merge.                                          |
| 5    | The job runs the tests from the archive on every `sdist` cell. A temporary import of `dev` in a test fails it.                                         |
| 6    | The new tests cover the script; the sdist holds neither of them, and the step of 4.6 passes.                                                           |
| 7    | `ci.yaml` passes on the released commit (`release-pypi.yaml` requires it), then `nightly-package.yaml`, run by hand, passes on the published package.  |

Test of step 1 (`tests/integration/test_manager_async.py`):
`test_handler_starts_a_background_task` (parametrized on the two triggers), "Test that a handler
that returns nothing leaves its task running after the trigger".

Gates before each merge: `ruff check src tests dev`, `ruff format src tests dev`, `ty check`,
`pyright`, `lint-imports`, `pytest tests/unit tests/integration --cov=minevent --cov-branch` at
100%, `inv test.doctest`, `mkdocs build --strict -f docs/mkdocs.yml` and
`python tests/package_checks.py`.

## 9. Decisions for the maintainers

### Changes of the library that were compared and rejected

- **D1. Let `trigger_event` accept a task or a future?** (Only a coroutine would raise.)
  _Recommended: no._ It would make `lambda _: loop.create_task(...)` work, but the error of a task
  that nobody reads is lost, an awaitable that is not scheduled would be dropped in silence, and
  `atrigger_event` would still await the task, so the two triggers would differ in one more way.
  One rule and one recipe (4.1) are simpler.
- **D2. Require a `bool` from a condition?** _Recommended: no._ It would catch a condition without
  `return`, which a type checker already reports. It would reject `numpy.bool_`, which is not a
  `bool` and is what a comparison of a NumPy loss returns, and the idiom
  `context.get("is_best")`. Rejecting `None` only breaks the same idiom.
- **D3. Give the handler the name of the event?** _Recommended: no._ A registration names one event,
  so `functools.partial` binds it where it is known. It would add a field to `Context` or a second
  call shape.
- **D4. Return a tuple from `events`, like `get_subscriptions`?** _Recommended: no._ It breaks code
  for a consistency that fixes no problem.
- **D5. Move the checks of `add_event_handler` into `Subscription`?** One place would check
  everything, also for a subscription built by hand. _Recommended: no._ The constructor is internal,
  and such a subscription is never `active`.
- **Support a signal handler that changes the manager, replace the dicts by tuples, collect the
  errors, run handlers concurrently**: no change, for the reasons of the design page and of the
  previous reviews (a removal would be O(n), or the dispatch would need a policy).

### Decisions that the plan needs

- **D6. Remove the package versions script?** _Decided: no._ The script stays, as a part of the
  layout shared with `coola` (P25), and gets its tests (4.7).
- **D7. Let `CLAUDE.md` allow a shared validator?** _Recommended: yes_ (4.3). Alternative: write the
  check of an event four times.
- **D8. Keep one reference page?** _Recommended: yes_ (4.4). Alternative: keep the module pages and
  delete `::: minevent`, which keeps `check_signature` in the reference and hides what is exported.
- **D9. Test the source distribution in CI now?** _Recommended: yes_ (4.6). It was postponed until
  the content was fixed (#915). The tests take about 2 s on a laptop.
- **D10. Where is the home of a rule?** _Recommended: the table of 4.3._ Alternative: the pages state
  everything and the docstrings only link, which leaves `help()` without the behaviour of an object.

## 10. Not covered

- **The non-goals of the design page** (event objects, priorities, wildcards, weak references,
  collected errors, concurrent dispatch): unchanged.
- **Return values of handlers** and **typed payloads**: need their own design if users ask.
- **The nightly benchmark.** The scheduled runs of 2026-11-19 to 2026-11-25 failed, all with the
  workflow before #878, and no scheduled run of the current one was read [verified]. The two results
  saved by the last of them come from different CPUs (AMD EPYC 9V45 and Intel Xeon 8370C), so a 50%
  threshold between two runs may report the runner and not the code [reading]. Read a week of runs,
  then decide between the threshold, a baseline on the same runner, and the trend table alone.
- **The queue of the CI**: when read, most recent runs of `ci.yaml` were queued or cancelled
  [verified]. It can delay step 7.
- **Material for MkDocs** announces its end of life on 2027-05-05 when it builds [verified]. The
  choice of its successor needs its own review.
- **The `bot-`, `release-` and `security-` workflows and the `.make/` subtree**: not reviewed,
  except where section 4 names them.

---

## Appendix: effect on the size of the repository

| Item                 | Today | Target | Why                          |
| -------------------- | ----: | -----: | ---------------------------- |
| exported names       |     7 |      7 | six names and `__version__`  |
| modules              |     5 |      5 | no change                    |
| runtime dependencies |     0 |      0 |                              |
| code lines of `src`  |   413 |    413 | docstrings only              |
| reference pages      |     5 |      1 | the module pages are deleted |
