# Architecture and Design Principles

This document describes the architecture and design principles of `minevent`.

## Properties

These properties hold for every release and each one is covered by tests.

| #   | Property                     | Statement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Enforced by                                                             |
| --- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| P1  | Small surface                | Events are strings, handlers are plain callables, the manager connects them. Six exported names and `__version__` (`EventManager`, `Subscription`, `Context`, `Condition`, `PeriodicCondition`, `AfterNCondition`). `EventManager` has 8 public members (`events`, `get_subscriptions`, `add_event_handler`, `on`, `trigger_event`, `atrigger_event`, `clear_event`, `reset`) and `__len__`, `__contains__`.                                                                                                                                                          | `test_init.py`                                                          |
| P2  | Cheap import                 | `import minevent` is cheap and has no side effect: standard library only, and not `logging`, `inspect`, `asyncio` or `importlib.metadata`, and it creates no `typing` object (`NamedTuple`, `Protocol`, `TypeVar`): the annotations are strings and `typing` is read under `TYPE_CHECKING` only (`inspect` is imported when the first handler is registered, the version on the first access of `__version__`). It starts no thread, reads no file, emits no warning and writes no log.                                                                               | `test_import.py` (modules and `typing` objects)                         |
| P3  | Events are strings           | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                                                                                                                                                                                                                                                                                                                                    | `test_manager.py`                                                       |
| P4  | Validated at the door        | A wrong type raises `TypeError` in the call that receives it, with a message that names the argument and the value: the event, the handler (must be callable) and the condition (`None` or callable) of `add_event_handler` and `on`. An invalid registration leaves the manager unchanged.                                                                                                                                                                                                                                                                           | `add_event_handler`, `on`, `test_manager.py`                            |
| P5  | Registration identity        | `add_event_handler` returns a new `Subscription` every time; the same callable can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`. `active` is `True` from the registration until the registration is removed, by whatever means.                                                                                                                                                                                                                                                                  | `Subscription`, `test_manager.py`                                       |
| P6  | Registration order           | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                                                                                                                                                                                                                                                                                                                           | the ordered `dict`, `test_manager.py`                                   |
| P7  | Snapshot dispatch            | `trigger_event` runs the registrations that exist when it starts. A registration **added** by a running handler takes effect at the next trigger. A registration **removed** before its turn (by `remove()`, `clear_event`, `reset` or a `once` claim) does not run: a removed registration never starts.                                                                                                                                                                                                                                                             | `Subscription._call`, `test_manager.py`                                 |
| P8  | Fail-fast with context       | An exception of a handler propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and the name of the handler (the function under a `functools.partial`), once per distinct pair. **No message and no `repr` of the package runs the `repr` of user data**: they name the function, never its arguments.                                                                                                                                                                                                  | `_describe`, `_add_error_note`, `test_manager.py`                       |
| P9  | `once` is at-most-once       | A `once` registration is removed by an atomic claim just before its handler runs, so it runs at most once whatever the number of threads. A false condition does not consume it (the condition is evaluated first); a handler that raises does consume it.                                                                                                                                                                                                                                                                                                            | `Subscription._call`, `test_manager_once.py`, `test_manager_threads.py` |
| P10 | Synchronous by default       | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop. An object with `async def __call__` is a coroutine handler like a coroutine function.                                                                                                                                                                                                                                                 | `_check_not_awaitable`, `test_manager_async.py`                         |
| P11 | Thread-safe registry         | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                                                                                                                                                                                                                                                                                                                            | `EventManager._lock`, `test_manager_threads.py`                         |
| P12 | No hidden state              | No global manager, no discovery, no side effect of a read. Zero runtime dependencies; the import is cheap (P2). A manager cannot be copied or pickled (`copy.copy`, `copy.deepcopy` and `pickle` raise the same `TypeError`).                                                                                                                                                                                                                                                                                                                                         | `__reduce__`, `test_manager.py`                                         |
| P13 | Payload is data              | `trigger_event(event, /, **payload)` copies the payload into one read-only `Context` per trigger, shared by the handlers. A handler with a parameter is called as `handler(context)`, a handler without parameter as `handler()`; the check counts parameters once, at registration, and never matches keys. Any key is allowed (`event`, `self`). The handler decides what a missing key means (`context[key]` or `context.get(key, default)`). Arguments that do not come from the payload are bound with `functools.partial`: the manager has no second mechanism. | `trigger_event`, `test_manager.py`                                      |
| P14 | Options are per registration | `once` and `condition` are keyword-only arguments of `add_event_handler` and `on`, with the same names, defaults and meaning in both. A condition is a function that returns a boolean, called once per trigger, before the handler: as `condition(context)` if it has a parameter, and as `condition()` otherwise (the rule of the handlers). The built-in conditions keep per-instance state and both have `reset()`.                                                                                                                                               | signatures, `test_manager.py`, `test_conditions.py`                     |
| P15 | Typed                        | Fully typed, `py.typed`, `ty check` clean, the values of a `Context` are typed `object`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `ty check` in CI                                                        |
| P16 | Fast and linear              | A trigger of one handler costs about 0.36 µs (0.56 µs if a handler takes the `Context`, which is built only then), each extra handler about 0.1 µs, a registration plus its removal about 0.65 µs (Python 3.14, laptop). Registering _k_ handlers and removing them in any order costs O(_k_) in total. Benchmarks guard it.                                                                                                                                                                                                                                          | `tests/benchmarks/`                                                     |
| P17 | A manager is a service       | `bool(manager)` is always `True`, empty or not, so `manager or default` means "is there a manager". `len(manager)` is the number of registrations.                                                                                                                                                                                                                                                                                                                                                                                                                    | `__bool__`, `test_manager.py`                                           |
| P18 | One way to do each thing     | One way to register (`add_event_handler`, with `on` as its decorator form), one way to bind arguments (`functools.partial`), one way to run a handler once (`once=True`, whatever the condition), one way to extend (write a callable). No handler base class.                                                                                                                                                                                                                                                                                                        | the signatures                                                          |
| P19 | Debuggable without a logger  | `repr(subscription)` names the event and the handler function (`Subscription(event='epoch_end', handler='log_epoch')`), `repr(manager)` counts the registrations per event. The library logs nothing: `get_subscriptions(event)` is the way to look.                                                                                                                                                                                                                                                                                                                  | `__repr__`, `test_manager.py`                                           |

## Overview

`minevent` is designed as a minimal event system with three core components:

1. **Events** - String identifiers representing things that happen
2. **Event Handlers** - Any callable that executes when events occur
3. **Event Manager** - Coordinator that manages handlers and triggers events

## Design Principles

### 1. Simplicity First

`minevent` prioritizes simplicity over features:

- Minimal API surface area
- Easy to understand and use
- No complex configuration required
- Clear separation of concerns

**Example**: Events are simply strings, not complex objects.

```python
# Simple and clear
manager.trigger_event("training_complete")

# Not: complex event objects
# manager.trigger_event(Event(name="training_complete", priority=1, ...))
```

### 2. Synchronous by Design

`trigger_event` is synchronous:

- Handlers execute in the order they were registered
- Easy to reason about execution flow
- Simpler debugging and testing
- Coroutine handlers are opt-in with `atrigger_event`
- The registry is protected by a lock, but the library starts no thread

**Rationale**: ML workflows are often sequential and benefit from deterministic execution order.

### 3. Explicit Over Implicit

All actions are explicit:

- Must explicitly register handlers
- Must explicitly trigger events
- Must explicitly pass arguments to handlers

**Example**:

```python
# Explicit registration
manager.add_event_handler("event", handler)

# Explicit triggering
manager.trigger_event("event")

# Not: implicit auto-registration or magic discovery
```

### 4. Extensibility Through Composition

Extend functionality by composing callables:

- A handler is any callable: a function, a method, a callable object or a `functools.partial`
- The options of a registration (`once`, `condition`) are arguments of
  `add_event_handler`
- No base class and no inheritance

**Example**:

```python
# Compose a handler with a condition, and bind an argument with functools.partial
manager.add_event_handler(
    "epoch_end",
    functools.partial(my_function, verbose=True),
    condition=PeriodicCondition(freq=5),
)


# Custom conditions: any function that returns a bool, with or without the context
class MyCondition:
    def __call__(self) -> bool:
        return custom_logic()
```

### 5. Zero Magic

No hidden behavior or surprising actions:

- No global state
- No automatic discovery
- No metaclasses and no discovery; the only introspection is the count of the parameters of
  a handler at registration (does it need the context?) and the check of an awaitable result
- What you write is what happens

## Core Components

### Event

**Design**: Events are represented as case-sensitive strings.

**Rationale**:

- Simple and universal
- Easy to type and understand
- No serialization issues
- Language-agnostic concept

**Best Practices**:

- Use descriptive names
- Follow consistent naming convention
- Use a namespace such as `training.batch.end` for complex systems (names are plain strings, so
  there is no hierarchy)

### Event Handler

**Design**: A handler is any callable. The manager calls it as `handler(context)` if it has a
parameter that accepts a positional argument, and as `handler()` otherwise.

**Rationale**:

- A callable already is the extension point: there is no base class to learn or to import
- Arguments that do not come from the payload are bound with `functools.partial`, so there is one
  way to bind them, and the parameter count sees the signature of the partial (the arguments that
  it binds are not counted)
- A handler that returns an awaitable (a coroutine function, or an object with
  `async def __call__`) is awaited by `atrigger_event`; `trigger_event` raises a `TypeError`
- A `Subscription` identifies a registration, so the same callable can be registered several times

### Event Manager

**Design**: Central coordinator using a dictionary to map events to ordered sets of subscriptions.

**Internal Structure**:

```python
{
    "event1": {subscription1: None, subscription2: None, subscription3: None},
    "event2": {subscription4: None, subscription5: None},
    # ...
}
```

**Rationale**:

- Simple dictionary lookup for handlers
- Preserves registration order
- Easy to implement and understand

**Key Operations**:

- `O(1)` handler registration
- `O(n)` event triggering (n = number of handlers)
- `O(1)` removal of a registration

## Registration Options

**Design**: The options of a registration are the keyword-only arguments of `add_event_handler`
(`on` is its decorator form, with the same options). The `Subscription` stores them.

**Architecture**:

```text
add_event_handler(event, handler, *, once=False, condition=None)
    └── Subscription (event, handler, once, condition)
```

**Execution Flow**:

```text
trigger_event()
    ├── Get the subscriptions of the event
    └── For each subscription:
        ├── If it has a condition: evaluate it, and skip the handler if it is False
        ├── If it is a once registration: remove it, and skip it if it was already removed
        └── Execute handler(context), or handler() if it has no parameter
```

**Rationale**:

- Separates "what" (handler) from "when" (condition) and from "how" (options)
- Conditions are reusable across handlers
- Conditions can maintain state between evaluations

## Event Flow

### Registration Flow

```text
1. User registers a callable
   subscription = manager.add_event_handler("event", handler, once=..., condition=...)

2. Manager validates the arguments
   a TypeError names the event, the handler or the condition that is wrong

3. Manager stores the registration
   a Subscription is added to the ordered set of the event and returned
```

### Triggering Flow

```text
1. User triggers event
   manager.trigger_event("event", **payload)

2. Manager gets the registrations
   subscriptions = a snapshot of the ordered set of the event
   context = Context(payload)   # one read-only context, shared by the handlers

3. Manager executes each handler
   for subscription in subscriptions:
       result = subscription._call(context)   # condition, once claim, handler(context) or handler()
       # an awaitable result raises a TypeError (trigger_event) or is awaited (atrigger_event)
       # an exception gets a note (event, handler function) and propagates
```

### Handler Execution

```text
Without condition:
    handler(context)      # or handler() if it has no parameter

With a condition:
    if condition():
        handler(context)

The context is read-only: a handler cannot change what the next handler sees.
Arguments bound with functools.partial are part of `handler`, not of the payload.
```

## Extension Points

### Custom Handlers

Write a callable. A class with a `__call__` method is a handler with its own state:

```python
class MyHandler:
    def __call__(self, context: Context) -> None:
        # Custom logic; context holds the keyword arguments of trigger_event
        pass


class MyAsyncHandler:
    async def __call__(self, context: Context) -> None:
        # Awaited by atrigger_event
        pass
```

**Use Cases**:

- Handlers with complex state
- Handlers that modify themselves
- Handlers with special lifecycle

### Custom Conditions

A condition is any function that returns a boolean (a `Condition`): `Callable[[], bool]`, or
`Callable[[Context], bool]` to decide from the payload of the trigger. Implement `__call__` in a
class when the condition has a state:

```python
class MyCondition:
    def __call__(self) -> bool:
        # Custom logic
        return some_condition
```

To combine conditions, write a function: `lambda: a() and b()` skips `b` when `a` is `False`, and
`lambda: all([a(), b()])` evaluates both.

**Use Cases**:

- Time-based conditions
- State-based conditions
- Metric-threshold conditions
- Complex multi-condition logic

## Not guaranteed

These behaviors are documented limits, not defects:

- **A removal in another thread.** P7 is exact in the thread that triggers: a handler that removes a
  later registration of the same trigger prevents it. Another thread that calls `remove()` while a
  trigger is between the check and the call of that handler cannot prevent that one start. After a
  trigger returns, a removed registration has not run.
- **Recursion.** A handler that triggers its own event recurses until `RecursionError`.
- **Blocking.** A synchronous handler in `atrigger_event` blocks the event loop.
- **A handler that returns a generator** (a `def` with `yield`) does nothing: the generator is
  never iterated. Only awaitables are detected (P10).
- **Prompt reclamation.** A manager that holds a registration is in a reference cycle (manager,
  dict, `Subscription`, manager): `del manager` does not free it until the garbage collector runs.
  Call `reset()` to release the handlers at a known point.
- **A callable whose signature cannot be inspected** is called as `handler(context)`. If it takes no
  argument, the call raises a `TypeError` with the note of the event and the handler: wrap it in a
  function without parameter.
- **A mutable value of the payload.** The `Context` is read-only, but its values are not copied: a
  handler that mutates a list is seen by the next handlers.

## Thread Safety

**Status**: `EventManager` protects its registry with a reentrant lock. Registering, removing and
inspecting handlers, and triggering events, can be done from several threads.

**Guarantees**:

- `trigger_event` runs the handlers of a snapshot taken under the lock; the handlers run outside the
  lock, in the calling thread, so a handler can use the manager.
- Handlers added or removed during a trigger take effect on the next trigger.

**Not guaranteed**:

- Handlers triggered from several threads run concurrently. A handler that shares state must
  protect it.
- The state of a condition (for example the counter of `PeriodicCondition`) is not protected, so a
  stateful condition should be triggered from one thread.

## Non-goals

`minevent` stays minimal. These features are not provided and are not planned:

- **Event objects** with metadata or priorities: events are plain strings, and data is given as
  keyword arguments to `trigger_event`.
- **Handler ordering** other than the registration order.
- **Weak references** or sender/receiver filtering.
- **Collecting handler errors**: handlers run fail-fast, and an exception stops the dispatch. To
  run every handler and report all the failures, wrap the handler in a `try`/`except` (an
  `ExceptionGroup` option such as `on_error="collect"` was considered and declined to keep
  `trigger_event` minimal).
