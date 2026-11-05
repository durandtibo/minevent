# Architecture and Design Principles

This document describes the architecture and design principles of `minevent`.

## Properties

These properties hold for every release and each one is covered by tests.

| #   | Property                 | Statement                                                                                                                                                                                                                                                     |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | Small surface            | Three concepts and plain callables. Seven exported names and `__version__`. `EventManager` has 9 public members.                                                                                                                                              |
| P2  | Events are strings       | An event name is a case-sensitive `str`; any other type raises `TypeError`. The empty string is valid. Reading the manager never creates an event.                                                                                                            |
| P3  | Validated at the door    | A wrong type raises `TypeError` in the call that receives it: the event, the handler of `add_event_handler`, the callable, the arguments and the condition of `EventHandler`.                                                                                 |
| P4  | Registration identity    | `add_event_handler` returns a new `Subscription` every time; the same handler can be registered several times. `remove()` removes that registration only, once: `True` the first time, then `False`.                                                          |
| P5  | Registration order       | The handlers of an event run in the order they were registered, one after the other, in the calling thread.                                                                                                                                                   |
| P6  | Snapshot dispatch        | `trigger_event` runs the registrations that exist when it starts. A registration added or removed by a running handler takes effect at the next trigger.                                                                                                      |
| P7  | Fail-fast with context   | An exception of a handler propagates unchanged (same object, same type); the remaining handlers are skipped. It carries a note with the event and the handler callable, once per distinct pair. Building the note never runs the `repr` of user data.         |
| P8  | `once` is at-most-once   | A `once` registration is removed before its handler is called, by an atomic claim: it runs at most once whatever the number of threads, and it is consumed even if its condition is false or its handler raises.                                              |
| P9  | Synchronous by default   | `trigger_event` never awaits; a handler that returns an awaitable raises `TypeError` and the coroutine is closed. `atrigger_event` awaits the handlers one after the other; synchronous handlers run inline and block the loop.                               |
| P10 | Thread-safe registry     | The registry is protected by a reentrant lock. Handlers, conditions and the `repr` of user objects run outside the lock, so a handler can use the manager.                                                                                                    |
| P11 | No hidden state          | No global manager, no discovery, no side effect of a read. Zero runtime dependencies. `import minevent` does not import `importlib.metadata`.                                                                                                                 |
| P12 | Payload is data          | `trigger_event(event, /, **payload)` passes the payload to every handler as keyword arguments, after `handler_kwargs`. Any key is allowed (`event`, `self`). With `filter_payload=True` only the keys the signature accepts are passed.                       |
| P13 | Conditions are callables | A condition is a `Callable[[], bool]`, called once per trigger and per handler, before the handler. The built-in conditions keep per-instance state; sharing an instance shares the state. There is one way to run a handler once (`once=True`).              |
| P14 | Typed                    | Fully typed, `py.typed`, `ty check` clean, payload typed `object`.                                                                                                                                                                                            |
| P15 | Fast and linear          | A trigger of one handler costs about 0.5 µs and each extra handler about 0.15 µs. Registering _k_ handlers and removing them in any order costs O(_k_) in total.                                                                                              |

## Overview

`minevent` is designed as a minimal event system with three core components:

1. **Events** - String identifiers representing things that happen
2. **Event Handlers** - Code that executes when events occur
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
manager.add_event_handler("event", EventHandler(handler))

# Explicit triggering
manager.trigger_event("event")

# Not: implicit auto-registration or magic discovery
```

### 4. Extensibility Through Composition

Extend functionality by composing handlers and conditions:

- Base classes for custom implementations
- An `EventHandler` combines a handler and an optional condition
- No inheritance-heavy design

**Example**:

```python
# Compose handlers with conditions
handler = EventHandler(my_function, condition=PeriodicCondition(freq=5))


# Custom conditions: any function without argument that returns a bool
class MyCondition:
    def __call__(self) -> bool:
        return custom_logic()
```

### 5. Zero Magic

No hidden behavior or surprising actions:

- No global state
- No automatic discovery
- No metaclasses and no discovery; the only introspection is the optional `filter_payload`
  (signature of the handler) and the check of an awaitable result
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
- Consider hierarchical naming for complex systems

### Event Handler

**Design**: Handlers wrap callable functions with optional arguments.

**Class Hierarchy**:

```
BaseEventHandler (abstract)
    ├── EventHandler (handler + arguments + optional condition)
    └── [Your custom handlers]
```

**Key Methods**:

- `handle(**payload)`: Execute the handler logic. `EventHandler.handle` raises a `TypeError` if
  the handler returns an awaitable.
- `ahandle(**payload)`: Execute the handler logic in a coroutine. `BaseEventHandler.ahandle` calls
  `handle()`; `EventHandler.ahandle` awaits the awaitable returned by the handler.

**Rationale**:

- Separation between handler logic and handler metadata
- Handlers are compared by identity; a `Subscription` identifies a registration
- Supports both simple and complex use cases

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

## Conditional Execution

**Design**: `EventHandler` can wrap a handler with a condition.

**Architecture**:

```
EventHandler(condition=...)
    ├── Handler (callable)
    └── Condition (callable that returns a bool)
```

**Execution Flow**:

```
trigger_event()
    ├── Get handlers for event
    └── For each handler:
        ├── If the handler has a condition:
        │   ├── Evaluate condition
        │   └── If True: execute handler
        └── Else: execute handler
```

**Rationale**:

- Separates "what" (handler) from "when" (condition)
- Conditions are reusable across handlers
- Conditions can maintain state between evaluations

## Event Flow

### Registration Flow

```
1. User creates EventHandler
   EventHandler(function, args, kwargs, condition=..., filter_payload=...)

2. User registers handler
   subscription = manager.add_event_handler("event", handler, once=...)

3. Manager stores the registration
   a Subscription is added to the ordered set of the event and returned
```

### Triggering Flow

```
1. User triggers event
   manager.trigger_event("event")

2. Manager gets the registrations
   subscriptions = a snapshot of the ordered set of the event

3. Manager executes each handler
   for subscription in subscriptions:
       if subscription is once and was already removed: skip it
       handler.handle(**payload)   # or `await handler.ahandle(**payload)`
       # an exception gets a note (event, handler function) and propagates
```

### Handler Execution

```
Without condition:
    handler(*handler_args, **handler_kwargs, **payload)

With a condition:
    if condition():
        handler(*handler_args, **handler_kwargs, **payload)

With filter_payload=True, `payload` only keeps the keys the handler accepts.
```

## Extension Points

### Custom Event Handlers

Implement `BaseEventHandler`:

```python
class MyEventHandler(BaseEventHandler):
    def handle(self, /, **payload: object) -> None:
        # Custom logic; payload holds the keyword arguments of trigger_event
        pass
```

**Use Cases**:

- Handlers with complex state
- Handlers that modify themselves
- Handlers with special lifecycle

### Custom Conditions

A condition is any function without argument that returns a boolean (the `Condition` protocol).
Implement `__call__` in a class when the condition has a state:

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

## Design Decisions

### Why Strings for Events?

**Alternatives Considered**:

- Enum types
- Custom Event classes
- Integer IDs

**Chosen**: Strings

**Reasons**:

- Universal and simple
- Easy to understand
- No import dependencies
- Flexible naming
- Human-readable

### Why Synchronous by Default?

**Alternatives Considered**:

- Async/await support
- Threading
- Multiprocessing

**Chosen**: Synchronous `trigger_event`, with `atrigger_event` for coroutine handlers

**Reasons**:

- Simpler to understand
- Easier to debug
- Deterministic execution
- Sufficient for ML workflows
- Coroutine handlers are opt-in with `atrigger_event`; `trigger_event` stays synchronous

### Why Explicit Event Manager?

**Alternatives Considered**:

- Global event bus
- Singleton manager
- Module-level functions

**Chosen**: Explicit manager instance

**Reasons**:

- No hidden global state
- Easier to test
- Multiple managers possible
- Clear ownership
- Explicit is better than implicit

## Conclusion

`minevent` is designed to be:

- **Simple**: Easy to learn and use
- **Explicit**: No surprises or magic
- **Extensible**: Customize through composition
- **Focused**: Does one thing well
- **Reliable**: Well-tested and documented

The architecture supports these goals while remaining flexible enough for diverse use cases in
machine learning and beyond.
