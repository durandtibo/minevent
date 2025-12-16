# Frequently Asked Questions (FAQ)

## General Questions

### What is minevent?

`minevent` is a minimal, lightweight event system for Python, designed specifically with Machine
Learning workflows in mind. It provides a simple way to add extensibility to your code by allowing
you to register event handlers that execute when specific events are triggered.

### Why should I use minevent?

`minevent` is useful when you want to:

- Add hooks or callbacks to your code without modifying its core logic
- Implement plugin-like functionality
- Separate concerns in your ML training pipelines
- Create extensible frameworks
- Add logging, monitoring, or debugging capabilities without cluttering your main code

### How is minevent different from other event systems?

`minevent` is designed to be minimal and focused. It:

- Has minimal dependencies (only requires `coola`)
- Is synchronous by design (simpler reasoning about execution order)
- Provides conditional event handling out of the box
- Is specifically tailored for ML workflows but works for any Python application

## Installation and Setup

### What Python versions are supported?

`minevent` currently supports Python 3.10 and above. See the compatibility table in the README for
specific version requirements.

### How do I install minevent?

The simplest way is via pip:

```shell
pip install minevent
```

For development or contributing, see the [Get Started](get_started.md) guide.

### Can I use minevent with other ML frameworks?

Yes! `minevent` is framework-agnostic and can be integrated with PyTorch, TensorFlow, scikit-learn,
or any other Python-based ML framework.

## Usage Questions

### How do I create a simple event handler?

```python
from minevent import EventHandler, EventManager


def my_handler():
    print("Event triggered!")


manager = EventManager()
manager.add_event_handler("my_event", EventHandler(my_handler))
manager.trigger_event("my_event")
```

### Can I pass arguments to event handlers?

Yes, use `handler_args` and `handler_kwargs`:

```python
from minevent import EventHandler


def greet(name: str, greeting: str="Hello"):
    print(f"{greeting}, {name}!")


handler = EventHandler(
    greet, handler_args=("Alice",), handler_kwargs={"greeting": "Hi"}
)
handler.handle()  # Prints: Hi, Alice!
```

### How do I execute a handler only sometimes?

Use `ConditionalEventHandler` with a condition:

```python
from minevent import ConditionalEventHandler, PeriodicCondition

# Execute only every 5 times
handler = ConditionalEventHandler(my_function, PeriodicCondition(freq=5))
```

### Can I add the same handler to multiple events?

Yes! You can register the same handler to different events:

```python
handler = EventHandler(my_function)
manager.add_event_handler("event1", handler)
manager.add_event_handler("event2", handler)
```

### How do I remove an event handler?

Use the `remove_event_handler` method:

```python
manager.remove_event_handler("my_event", handler)
```

### What happens if I trigger an event with no handlers?

Nothing! The `trigger_event` method safely handles events with no registered handlers - it simply
does nothing and updates the last triggered event name.

### Can I check if a handler is already registered?

Yes, use `has_event_handler`:

```python
if not manager.has_event_handler(handler, "my_event"):
    manager.add_event_handler("my_event", handler)
```

### Are event handlers executed in order?

Yes! Event handlers are executed in the order they were registered using `add_event_handler`.

### Is minevent thread-safe?

No, `minevent` is not thread-safe by design. It is intended for synchronous, single-threaded use
cases. If you need thread-safe event handling, consider using locks or other synchronization
mechanisms.

## Advanced Questions

### Can I create custom conditions?

Yes! Implement the `BaseCondition` class:

```python
from minevent.conditions import BaseCondition


class MyCondition(BaseCondition):
    def evaluate(self) -> bool:
        # Your custom logic here
        return some_condition

    def equal(self, other) -> bool:
        return isinstance(other, MyCondition)
```

### Can I create custom event handlers?

Yes! Implement the `BaseEventHandler` class:

```python
from minevent.handlers import BaseEventHandler


class MyEventHandler(BaseEventHandler):
    def handle(self) -> None:
        # Your custom logic here
        pass

    def equal(self, other) -> bool:
        return isinstance(other, MyEventHandler)
```

### How do I integrate minevent into my training loop?

Here's a common pattern for ML training:

```python
from minevent import EventManager, EventHandler


def train(epochs, manager):
    manager.trigger_event("training_start")

    for epoch in range(epochs):
        manager.trigger_event("epoch_start")

        # Training logic here
        for batch in data_loader:
            manager.trigger_event("batch_start")
            # Process batch
            manager.trigger_event("batch_end")

        manager.trigger_event("epoch_end")

    manager.trigger_event("training_end")


# Setup handlers
manager = EventManager()
manager.add_event_handler("epoch_end", EventHandler(save_checkpoint))
manager.add_event_handler("training_end", EventHandler(log_metrics))

train(epochs=10, manager=manager)
```

### Can event handlers modify the event manager?

Yes, but be cautious! An event handler can add or remove other handlers, but modifying the handlers
of the currently firing event during its execution is not recommended as it may lead to unexpected
behavior.

### What is the performance overhead of using minevent?

`minevent` is designed to be lightweight with minimal overhead. The main cost is the function call
overhead for each registered handler. For most ML workflows, this overhead is negligible compared to
the computation time of training operations.

## Troubleshooting

### I get "RuntimeError: event does not exist" when removing a handler

This means you're trying to remove a handler from an event that hasn't been registered. Make sure:

1. The event name matches exactly (event names are case-sensitive)
2. At least one handler has been added to that event before trying to remove one

### My handler isn't being called

Check that:

1. You've registered the handler with `add_event_handler`
2. You're triggering the correct event name (case-sensitive)
3. If using `ConditionalEventHandler`, the condition evaluates to `True`
4. The handler function is callable and doesn't raise exceptions

### How do I debug event handlers?

Add logging to your handlers:

```python
import logging


def my_handler():
    logging.info("Handler called")
    # Your logic here
```

Or check the event manager state:

```python
print(manager)  # Shows all registered handlers
print(manager.last_triggered_event)  # Shows last triggered event
```

## Getting Help

### Where can I report bugs or request features?

Please use the [GitHub issue tracker](https://github.com/durandtibo/minevent/issues) to report bugs
or request features.

### How can I contribute?

See the [Contributing Guide](https://github.com/durandtibo/minevent/blob/main/.github/CONTRIBUTING.md)
for information on how to contribute to `minevent`.

### Where can I find more examples?

Check the [quickstart guide](quickstart.md) and the examples in the `examples/` directory of the
repository.
