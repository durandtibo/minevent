# Architecture and Design Principles

This page is the reference of the rules of `minevent`: the properties that it guarantees, the
behaviors that it does not guarantee, the rule that calls the handlers and the reasons of the design.
The [quickstart](quickstart.md) is the first contact, the [examples](examples.md) are runnable
recipes and the [user guide](guide.md) gives the recommendations.

## Properties

These properties hold for every release and each one is covered by tests.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Enforced by                                                              |
| --- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.                                                                                                                                                         | `test_init.py`                                                           |
| P2  | Cheap import                 | `import minevent` is cheap and has no side effect: standard library only, and not `logging`, `inspect`, `asyncio` or `importlib.metadata`, and it creates no `typing` object (`NamedTuple`, `Protocol`, `TypeVar`): the annotations are strings and the names that only a type checker needs are imported under `TYPE_CHECKING` (`inspect` is imported when the first handler is registered, the version on the first access of `__version__`). It starts no thread, reads no file, emits no warning and writes no log.                                              | `test_import.py` (modules and `typing` objects)                          |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                                                                                                                                                                                                                                   | `test_manager.py`                                                        |
| P4  | Validated at the door        | `add_event_handler` and `on` reject, with a `TypeError` that names the argument and the value: a non-`str` event, a non-callable handler or condition, a signature that P13 rejects, and a generator or async generator function. A rejected registration leaves the manager unchanged. The annotations of a handler or a condition do not have to be resolvable.                                                                                                                                                                                                    | `add_event_handler`, `calls.needs_context`, `test_manager.py`            |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only: `True` the first time, then `False`. `active` is `True` until the registration is removed, by whatever means.                                                                                                                                                                                                                                                                                             | `Subscription`, `test_manager.py`                                        |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                                                                                                                                                                                                                          | the ordered `dict`, `test_manager.py`                                    |
| P7  | Snapshot dispatch            | A trigger visits the registrations that exist when it starts. A registration **added** by a running handler takes effect at the next trigger. A registration **removed** before its turn (by `remove()`, `clear_event`, `reset` or a `once` claim) does not run.                                                                                                                                                                                                                                                                                                     | `Subscription._call`, `test_manager.py`                                  |
| P8  | Fail-fast with context       | An exception of a handler or a condition propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and the function of the handler (under a `functools.partial`), once per distinct pair. No message and no `repr` of the package runs the `repr` of user data to name a handler.                                                                                                                                                                                                                          | `calls.add_error_note`, `test_calls.py`, `test_manager.py`               |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim just before its handler is called, after its condition, so it is called at most once whatever the number of threads. A false or raising condition does not consume it; a handler that raises does.                                                                                                                                                                                                                                                                                                               | `Subscription._call`, `test_manager_once.py`, `test_manager_threads.py`  |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError`. `atrigger_event` awaits the handlers one after the other (an object with `async def __call__` is a coroutine handler too). **Conditions are synchronous in both**: a condition that returns an awaitable raises `TypeError`. A coroutine that is rejected is closed.                                                                                                                                                                                                           | `calls.reject_awaitable`, `Subscription._call`, `test_manager_async.py`  |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                                                                                                                                                                                                                                                                                                                           | `EventManager._lock`, `test_manager_threads.py`                          |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependency. A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`).                                                                                                                                                                                                                                                                                                                                                                    | `__reduce__`, `test_manager.py`                                          |
| P13 | Two calls                    | A handler and a condition are called as `f()` or `f(context)`. **A parameter that has a default keeps it: the manager never fills it.** A callable whose other parameters are none is called as `f()`; one with exactly one other parameter, positional, is called as `f(context)`; any other signature (including `*args` and `**kwargs`), or one that cannot be inspected, is rejected (P4). Names and annotations are not checked. The signature is the one that `inspect.signature` reports, read once, at registration ([the calling rule](#the-calling-rule)). | `calls.needs_context`, `test_calls.py`                                   |
| P14 | Payload is data              | `trigger_event(event, context=None, /)` copies the mapping `context` (a dict, for example), or reuses a `Context` as is, into one read-only `Context` per trigger, shared by the handlers and the conditions. A `Context` can be copied, deep-copied and pickled (protocol 2 or higher) if its values can; the values are not copied by the context itself. Any `str` key is allowed, it does not need to be a valid identifier. The handler decides what a missing key means (`context[key]` or `context.get(key, default)`).                                       | `trigger_event`, `Context`, `test_context.py`                            |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean. The values of a `Context` are `Any`, so the documented handlers type check in the code of a user.                                                                                                                                                                                                                                                                                                                                                                                                                         | `ty check` in CI, `test_context_typing.py`                               |
| P16 | Fast and linear              | About 0.3 µs for a trigger with one trivial handler, 0.1 µs for each extra one, 0.75 µs with a small dict (it is copied into a `Context`), and 4.5 µs for a registration plus its removal (the signature is inspected there, never in a trigger). Reading a value of a `Context` costs the same, present or missing, whatever the number of keys (`get` and `in`; `context[key]` lists the keys in its `KeyError`). Registering _k_ handlers and removing them in any order costs O(_k_). Measured on a laptop with Python 3.14.                                     | `tests/benchmarks/`                                                      |
| P17 | A manager is a service       | `bool(manager)` is always `True`, empty or not, so `manager or default` means "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                                                                                                                                                                                                                                                                                   | `__bool__`, `test_manager.py`                                            |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form and the same keyword-only options `once` and `condition`), one way to adapt a callable (wrap it in a function, a lambda or a `functools.partial` that needs nothing or only the context), one way to run once (`once=True`), one way to extend (write a callable). No handler base class. One page states each rule.                                                                                                                                                                       | the signatures, the documents                                            |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function (`Subscription(event='epoch_end', handler='log_epoch')`), `repr(manager)` counts the registrations per event. The library logs nothing: `get_subscriptions(event)` is the way to look.                                                                                                                                                                                                                                                                                                                 | `__repr__`, `test_manager.py`                                            |
| P20 | Everything that runs, is run | Each pull request runs the unit and integration tests, the doctests, `tests/package_checks.py` and one pass of every benchmark (except the import benchmarks, which need the statistics and run on a schedule), so a change of the API cannot leave one of them behind.                                                                                                                                                                                                                                                                                              | `ci.yaml`, `test_package_checks.py`                                      |
| P21 | Exact built-in conditions    | `PeriodicCondition` and `AfterNCondition` count every call once, from any number of threads, with and without the GIL. They can be copied and pickled: a copy starts at the same step and has its own counter.                                                                                                                                                                                                                                                                                                                                                       | `_CountingCondition`, `test_conditions.py`, `test_conditions_threads.py` |

## The Calling Rule

A handler is written as `def g()` or `def g(context: Context)`, and any callable that can be called
in one of these two ways works: **the parameters that have a default are ignored.** The same rule
applies to a condition, which returns a boolean. It is checked once, at registration.

| Parameters without default            | Example                            | Result       |
| ------------------------------------- | ---------------------------------- | ------------ |
| none: no parameter                    | `def g()`                          | `g()`        |
| none: only positional with defaults   | `model.train`, `lambda i=i: ...`   | `g()`        |
| none: only keyword-only with defaults | `def g(*, v=1)`, `partial(f, v=1)` | `g()`        |
| one, positional                       | `def g(context)`                   | `g(context)` |
| one, positional, then defaults        | `def g(context, verbose=False)`    | `g(context)` |
| `*args`, with or without `**kwargs`   | `print`, `Mock()`, `AsyncMock()`   | `TypeError`  |
| `**kwargs`                            | `def g(**kw)`                      | `TypeError`  |
| cannot be inspected                   | `max`, `dict.update`               | `TypeError`  |
| two or more                           | `def g(a, b)`                      | `TypeError`  |
| one, keyword-only                     | `def g(*, epoch)`                  | `TypeError`  |
| (any) generator or async generator    | `def g(): yield`                   | `TypeError`  |

Coroutine functions, bound methods, callable objects, classes and `functools.partial` objects follow
the same table. The signature of a partial does not contain the arguments that it binds.

To adapt a callable, wrap it in a function, a lambda or a `functools.partial`:

```python
manager.add_event_handler("epoch_start", model.train)  # model.train()
manager.add_event_handler("epoch_start", lambda: model.train(mode=True))  # a chosen value
manager.add_event_handler("batch_end", lambda context: print(context))  # print the context
manager.add_event_handler("epoch_end", functools.partial(save, "model.pt"))  # save(path, context)
```

In a test, `unittest.mock.create_autospec(func)` replaces `Mock()`: it has the signature of `func`.

A lambda created in a loop reads the loop variable when it is **called**, but a default value is
evaluated when the lambda is **created**. So `lambda i=i: print(i)` saves the current value, and it
is called without argument. A handler that needs a saved value **and** the context takes the context
first, without default: `lambda context, i=i: print(i, context["epoch"])`.

## Not guaranteed

These behaviors are documented limits, not defects:

- **A removal in another thread.** P7 is exact in the thread that triggers. A `remove()` from another
  thread cannot stop a handler that the trigger is about to call.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A callable object whose `__call__` is a generator**, and a function that _returns_ a generator,
  do nothing. Only generator _functions_ are rejected (P4) and awaitables detected (P10).
- **A coroutine handler registered with `once=True` and triggered with `trigger_event`** is consumed:
  the `TypeError` is raised after the call.
- **An optional parameter never receives the context.** `def f(context=None)` is called as `f()` and
  gets `None`, without an error: the context needs a parameter without default.
- **A decorated function** is judged by the signature that `inspect.signature` reports: with
  `functools.wraps`, that is the signature of the wrapped function.
- **An exception class that forbids new attributes** (a `frozen=True` dataclass exception) is
  replaced by the error of `add_note`.
- **A mutable value of the payload** can be mutated by a handler, and the next ones see it.
- **Threads.** The handlers run in the thread that triggers the event, concurrently if several
  threads trigger it, so a handler that shares state must protect it. The state of a condition of a
  user is not protected: only the built-in conditions are (P21).
- **Prompt reclamation.** A manager with registrations is in a reference cycle (manager, dict,
  `Subscription`, manager): `del manager` does not free it until the garbage collector runs.
  `reset()` releases the handlers at a known point.

## Design Notes

- **Events are strings.** They are easy to type, to read and to serialize. A namespace such as
  `training.batch.end` is a naming convention: there is no hierarchy.
- **A callable is the extension point.** There is no base class to learn or to import. The
  introspection is limited to the signature at registration and to the awaitable results.
- **Synchronous and sequential.** The handlers run in a deterministic order, which suits the
  sequential workflows of Machine Learning and is easy to debug. Coroutine handlers are opt-in with
  `atrigger_event`. The library starts no thread.
- **The registry** maps each event to an ordered `dict` of subscriptions used as an ordered set, so
  a registration and a removal are O(1), and a trigger is linear in the handlers of the event. A
  reentrant lock protects it, and a trigger takes a snapshot under the lock and runs it outside.
- **The `Subscription` is the registration.** It stores the handler and the options, so the same
  callable can be registered several times and each registration is removed on its own.

## Non-goals

`minevent` stays minimal. These features are not provided and are not planned:

- **Event objects** with metadata or priorities: events are plain strings, and data is given as a
  dict (or a `Context`) to `trigger_event`.
- **Handler ordering** other than the registration order.
- **Weak references** or sender/receiver filtering.
- **Collecting handler errors**: handlers run fail-fast, and an exception stops the dispatch. To run
  every handler and report all the failures, wrap the handler in a `try`/`except` (an
  `ExceptionGroup` option such as `on_error="collect"` was considered and declined to keep
  `trigger_event` minimal).
