# Architecture and Design Principles

This document describes the architecture and design principles of `minevent`.

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

All event handling is synchronous:

- Handlers execute in the order they were registered
- Easy to reason about execution flow
- Simpler debugging and testing
- No threading complexity; coroutine handlers are opt-in with `atrigger_event`

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
- Conditional handlers combine handlers and conditions
- No inheritance-heavy design

**Example**:

```python
# Compose handlers with conditions
handler = EventHandler(my_function, condition=PeriodicCondition(freq=5))


# Custom conditions by implementing BaseCondition
class MyCondition(BaseCondition):
    def evaluate(self) -> bool:
        return custom_logic()
```

### 5. Zero Magic

No hidden behavior or surprising actions:

- No global state
- No automatic discovery
- No reflection or metaclasses
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

- `handle()`: Execute the handler logic
- `equal()`: Compare handlers for equality

**Rationale**:

- Separation between handler logic and handler metadata
- Enables handler comparison for deduplication
- Supports both simple and complex use cases

### Event Manager

**Design**: Central coordinator using a dictionary to map events to handler lists.

**Internal Structure**:

```python
{
    "event1": [handler1, handler2, handler3],
    "event2": [handler4, handler5],
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
- `O(n)` handler lookup (n = total handlers)

## Conditional Execution

**Design**: `EventHandler` can wrap a handler with a condition.

**Architecture**:

```
EventHandler(condition=...)
    ├── Handler (callable)
    └── Condition (BaseCondition)
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
   EventHandler(function, args, kwargs)

2. User registers handler
   manager.add_event_handler("event", handler)

3. Manager stores handler
   _event_handlers["event"].append(handler)
```

### Triggering Flow

```
1. User triggers event
   manager.trigger_event("event")

2. Manager updates state
   _last_triggered_event = "event"

3. Manager gets handlers
   handlers = _event_handlers["event"]

4. Manager executes each handler
   for handler in handlers:
       handler.handle()
```

### Handler Execution

```
Without condition:
    handler(*handler_args, **handler_kwargs, **payload)

With a condition:
    if condition.evaluate():
        handler(*handler_args, **handler_kwargs, **payload)
```

## Extension Points

### Custom Event Handlers

Implement `BaseEventHandler`:

```python
class MyEventHandler(BaseEventHandler):
    def handle(self) -> None:
        # Custom logic
        pass

    def equal(self, other: Any) -> bool:
        # Custom comparison
        return isinstance(other, MyEventHandler)
```

**Use Cases**:

- Handlers with complex state
- Handlers that modify themselves
- Handlers with special lifecycle

### Custom Conditions

Implement `BaseCondition`:

```python
class MyCondition(BaseCondition):
    def evaluate(self) -> bool:
        # Custom logic
        return some_condition

    def equal(self, other: Any) -> bool:
        # Custom comparison
        return isinstance(other, MyCondition)
```

**Use Cases**:

- Time-based conditions
- State-based conditions
- Metric-threshold conditions
- Complex multi-condition logic

### Custom Event Manager

While not common, you can create custom event managers:

```python
class MyEventManager:
    # Must implement the same interface
    def add_event_handler(self, event: str, handler: BaseEventHandler): ...
    def trigger_event(self, event: str): ...
    def has_event_handler(self, handler: BaseEventHandler, event: str | None): ...
    def remove_event_handler(self, event: str, handler: BaseEventHandler): ...
    def reset(self): ...
```

**Use Cases**:

- Thread-safe event managers
- Event managers with persistence
- Event managers with priorities
- Event managers with event history

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

### Why Synchronous Only?

**Alternatives Considered**:

- Async/await support
- Threading
- Multiprocessing

**Chosen**: Synchronous

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
