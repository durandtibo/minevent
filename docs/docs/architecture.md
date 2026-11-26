# How It Works

This page describes the parts of `minevent`, what happens when you register a handler and trigger an
event, and the behavior that you can rely on. The reasons of these rules, and their trade-offs, are
on the [design choices page](design.md). The [quickstart](quickstart.md) is the first contact, the
[examples](examples.md) are runnable recipes and the [user guide](guide.md) gives the
recommendations.

## Overview

| Name                | Role                                                                             |
| ------------------- | -------------------------------------------------------------------------------- |
| event               | A case-sensitive `str` that names something that happens.                        |
| `Handler`           | A callable that runs when the event happens, called as `f()` or `f(context)`.    |
| `EventManager`      | Stores the registrations and triggers the events.                                |
| `Subscription`      | The registration of one handler to one event: it holds the options and `remove`. |
| `Context`           | The read-only payload of one trigger.                                            |
| `Condition`         | A synchronous function that returns a boolean and decides if a handler runs.     |
| `PeriodicCondition` | A condition that is `True` on one call in `freq`.                                |
| `AfterNCondition`   | A condition that is `False` for the first `n` calls, then `True`.                |

These seven names (all but "event") and `__version__` are what `minevent` exports. `EventManager`
has the following members:

| Member                                                                   | Use                                    |
| ------------------------------------------------------------------------ | -------------------------------------- |
| `add_event_handler(event, handler, *, once=False, condition=None)`       | Register a handler.                    |
| `on(event, *, once=False, condition=None)`                               | Register a function with a decorator.  |
| `trigger_event(event, context=None, /)`                                  | Run the handlers of an event.          |
| `atrigger_event(event, context=None, /)`                                 | Same, and await the coroutine handlers |
| `events`, `get_subscriptions(event)`, `event in manager`, `len(manager)` | Look at the registrations.             |
| `clear_event(event)`, `reset()` (and `remove()` of a `Subscription`)     | Remove registrations.                  |

## Registration

`add_event_handler` does the following, once:

1. It checks that the event is a `str`, that the handler and the condition (if any) are callable,
   and that `once` is a `bool` (not `1` or `"yes"`).
2. It reads the signature of the handler and of the condition to decide how to call each of them
   (see [the calling rule](#the-calling-rule)). It also rejects a generator function, and a
   coroutine function used as a condition. A callable object is judged by its `__call__`. It
   remembers whether the handler is a coroutine function.
3. It creates a `Subscription` and appends it to the registrations of the event.

Every rejection is a `TypeError` that says which argument is wrong, and it leaves the manager
unchanged. The same callable can be registered several times: each call returns a new
`Subscription`, and each registration runs and is removed on its own.

The registration lasts until `subscription.remove()`, the end of a `with subscription:` block,
`clear_event`, `reset`, or, with `once=True`, the first call of the handler.

## Trigger

```text
trigger_event(event, context)
    |   take a snapshot of the registrations of the event
    |   build one Context from the context (a Context is used as is)
    |   trigger_event only: a coroutine function as handler in the snapshot -> TypeError
    v
for each registration of the snapshot, in registration order:
    removed since the snapshot?          -> skip
    has a condition that is False?       -> skip
    removed by its condition?            -> skip
    once=True?                           -> remove the registration, or skip if already removed
    call handler() or handler(context)
    the handler returned an awaitable?   -> trigger_event raises, atrigger_event awaits it
```

If a condition or a handler raises, the trigger stops: the exception reaches the caller, and the
next registrations are skipped. Triggering an event that has no handler does nothing (the event and
the context are still checked).

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

Names and annotations are not checked. Coroutine functions, bound methods, callable objects, classes
and `functools.partial` objects follow the same table. The signature is the one that
`inspect.signature` reports: the signature of a partial does not contain the positional arguments
that it binds, and a decorator that uses `functools.wraps` has the signature of the wrapped
function. For the generator and coroutine checks, a callable object is judged by its `__call__` (a
partial by its function): an object whose `__call__` yields is rejected like a generator function.

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

## Behavior You Can Rely On

### Events and registrations

- An event name is a case-sensitive `str`. A `StrEnum` member is a `str`, and is kept as given. The
  empty string is valid. The methods of the manager raise a `TypeError` for another type, while `in`
  answers like a dict (`1 in manager` is `False`).
- Reading the manager never creates an event: `events` lists the events that have at least one
  registration.
- `subscription.remove()` removes that registration only. It returns `True` the first time, then
  `False`. `subscription.active` is `True` exactly while the registration is in the manager, so it
  becomes `False` when the registration is removed, by whatever means. A `Subscription` cannot be
  copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise a `TypeError`), and the manager
  alone creates one.
- `bool(manager)` is always `True`, empty or not, and `len(manager)` is the number of
  registrations. A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle`
  raise a `TypeError`).

### Dispatch

- The handlers of an event run in the order they were registered, one after the other, in the calling
  thread.
- A trigger visits the registrations that exist when it starts. A registration **added** by a
  running handler takes effect at the next trigger. A registration **removed** before its handler is
  called (by `remove()`, `clear_event`, `reset` or a `once` claim) does not run, whoever removed it:
  another handler, or its own condition.
- A condition is called just before its handler, so it sees the effects of the handlers that ran
  before.
- A `once` registration is removed by an atomic claim just before its handler is called, after its
  condition, so it is called at most once whatever the number of threads. A false or raising
  condition does not consume it; a handler that raises does.

### Payload

- `trigger_event(event, context)` copies the mapping `context` (a dict, for example), or reuses a
  `Context` as is, into one read-only `Context` per trigger, shared by the handlers and the
  conditions. Both arguments are positional-only.
- Any `str` key is allowed, it does not need to be a valid identifier. Another key raises a
  `TypeError`. The mapping is read once: the keys that are checked are the keys that are stored.
- The values are not copied. A `Context` can be copied, deep-copied and pickled (protocol 2 or
  higher) if its values can.
- A `Context` is equal to a mapping that has the same items, and it is not hashable.

### Errors

- An exception of a handler or a condition propagates unchanged (same object, same type), and the
  remaining handlers are skipped.
- An `Exception` carries a note with the event and what raised it: the handler, or the condition and
  its handler (each named by its function, under a `functools.partial`). The same note is not added
  twice. An exception that cannot take a note (a frozen dataclass exception, for example) propagates
  without it. A `BaseException` that is not an `Exception`, such as `KeyboardInterrupt` or
  `asyncio.CancelledError`, has no note.
- The messages of `minevent` do not run the `repr` of your objects to name a callable. Naming one
  never raises in place of your exception: the name of its class is used if its own name cannot be
  read.
- The messages of `minevent` stay short whatever the size of your data: a value is shown with
  [`reprlib`](https://docs.python.org/3/library/reprlib.html), and the `KeyError` of a `Context`
  lists at most 20 keys.

### Coroutines

- `trigger_event` never awaits. If a registration of the snapshot has a coroutine function as
  handler, it raises a `TypeError` before any condition or handler runs, whatever the conditions
  would answer. Any other handler that returns an awaitable raises a `TypeError` after its call.
- `atrigger_event` awaits what a handler returns, if it is awaitable, before it calls the next
  handler. It also runs the synchronous handlers.
- Conditions are synchronous in both: a coroutine function, or an object whose `__call__` is one,
  is rejected at registration, and a condition that returns an awaitable raises a `TypeError` at the
  trigger.
- A coroutine that is rejected is closed, so it does not emit a "never awaited" warning.

### Threads

- Registering, removing, triggering and reading the manager are safe from several threads, with and
  without the GIL.
- Your code (handlers, conditions, `repr` and finalizers) runs outside the lock of the manager, so
  it can use the manager.
- `PeriodicCondition` and `AfterNCondition` count every call once, from any number of threads. They
  can be copied and pickled: a copy starts at the same step and has its own counter.

### Import and typing

- `minevent` uses the standard library only. `import minevent` starts no thread, emits no warning
  and writes no output and no log. It reads `__version__` from the metadata of the installed
  package.
- The package is fully typed (`py.typed`). A handler argument is typed `Handler`, so a type checker
  reports a callable that needs two arguments, a keyword-only argument or an argument of another
  type than `Context`. The run-time check of the calling rule stays the authority. The values of a
  `Context` are typed `Any`.

## Limits

`minevent` does not protect against the following:

- **A removal in another thread** cannot stop a handler whose trigger has already checked that it is
  registered.
- **Concurrent calls.** A registration without `once` is called by every thread that triggers its
  event, possibly at the same time. A handler or a condition of yours that shares state must protect
  it.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A hidden coroutine.** A lambda, or a synchronous `functools.wraps` wrapper, that returns a
  coroutine is only detected after its call by `trigger_event`: the handlers before it have run, and
  a `once` registration is consumed.
- **Hidden generators.** A function that returns a generator, such as a lambda that calls a
  generator function, does nothing.
- **An optional parameter never receives the context.** `def f(context=None)` is called as `f()` and
  gets `None`, without an error: the context needs a parameter without default.
- **A signature that depends on Python.** The standard library adds signatures to C callables
  between versions: `set.add` is rejected on Python 3.11 and 3.12, and accepted from 3.13.
- **A condition counts its calls, not the triggers.** It is not called when an earlier handler
  raised, nor for a removed registration.
- **A huge integer in a message** on Python 3.11 and 3.12: showing an integer of more than 4,300
  digits (a value given as a handler, a key) raises the `ValueError` of Python instead of the error
  of `minevent`.
- **A mutable value of the payload** can be mutated by a handler, and the next ones see it.
- **Delayed release.** A manager with registrations is in a reference cycle (manager, registry,
  `Subscription`, manager): `del manager` does not free it until the garbage collector runs.
  `reset()` releases the handlers at a known point.

## Performance

The registry maps each event to an ordered `dict` of subscriptions, used as an ordered set:

- registering and removing a handler are O(1), whatever the number of handlers;
- a trigger is linear in the number of handlers of its event, and the other events cost nothing;
- the signature is inspected at registration, never during a trigger;
- a mapping given to a trigger is copied (linear in its number of keys), while a `Context` is not;
- `context.get(key, default)` and `key in context` cost the same for a present key and a missing
  one. `context[key]` lists up to 20 keys in its `KeyError`, so a missing key costs more.

As an order of magnitude, measured on a laptop with Python 3.14: about 0.3 µs for a trigger with one
trivial handler, 0.07 µs for each extra one, 0.8 µs with a small dict, and 5.5 µs for a registration
plus its removal. Measure on your machine with `inv test.benchmark` in a
[source installation](get_started.md#installing-from-source).
