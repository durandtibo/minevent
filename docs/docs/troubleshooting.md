# Troubleshooting

This guide helps you diagnose and resolve common issues when using `minevent`.

## Common Issues

### Event Handler Not Executing

**Symptoms**: You trigger an event but the handler doesn't execute.

**Possible Causes and Solutions**:

1. **Handler not registered**

   ```python
   # Check the registrations of the event
   print(manager.get_subscriptions("my_event"))  # () if no handler is registered
   print("my_event" in manager)
   ```

2. **Wrong event name** (event names are case-sensitive)

   ```python
   # These are different events!
   manager.add_event_handler("MyEvent", handler)
   manager.trigger_event("myevent")  # Won't trigger - different case!

   # Solution: Use consistent naming
   EVENT_NAME = "my_event"
   manager.add_event_handler(EVENT_NAME, handler)
   manager.trigger_event(EVENT_NAME)
   ```

3. **Conditional handler condition is False**

   ```python
   # Check condition state
   condition = PeriodicCondition(freq=5)
   handler = EventHandler(my_function, condition=condition)

   # The handler only executes every 5 calls
   for i in range(10):
       manager.trigger_event("my_event")
       print(f"Call {i}: Condition evaluated to {condition()}")
   ```

4. **Handler raises an exception**

   ```python
   # Add error handling to debug
   def safe_handler():
       try:
           my_function()
       except Exception as e:
           print(f"Handler error: {e}")
           import traceback

           traceback.print_exc()


   manager.add_event_handler("my_event", EventHandler(safe_handler))
   ```

### Removing a Handler That Is Already Removed

**Symptoms**: `subscription.remove()` returns `False`.

**Cause**: The registration was already removed: by `remove()`, by `clear_event` or `reset`, or
because it was registered with `once=True` and the event was triggered.

**Solution**: This is not an error. Use `subscription.active` to check if the handler is still
registered.

### Cannot Find a Handler to Remove

**Symptoms**: You did not keep the `Subscription` returned by `add_event_handler`.

**Cause**: Event handlers are compared by identity, so a new `EventHandler` built with the same
arguments is a different object.

**Solution**: Look at the registrations of the event and remove the one you want:

```python
for subscription in manager.get_subscriptions("my_event"):
    if subscription.event_handler.handler is my_function:
        subscription.remove()
```

### Memory Leaks

**Symptoms**: Memory usage grows over time in long-running applications.

**Cause**: A registered handler stays alive as long as the manager does. `EventHandler(obj.method)`
keeps `obj` alive, and so do `handler_args` and closures. `minevent` does not use weak references
(see the non-goals in the architecture page), so unsubscribe handlers you no longer need.

**Solution**:

```python
# Keep the Subscription and remove it when the owner is done
subscription = manager.add_event_handler("event", EventHandler(obj.method))
# Later...
subscription.remove()  # `obj` can be garbage collected


# Or scope the registration to a block
with manager.add_event_handler("event", EventHandler(obj.method)):
    run_phase()

# Clear all the handlers of an event, or of the manager
manager.clear_event("event")
manager.reset()
```

If a handler must not keep an object alive, give it a `weakref` and do nothing when the object is
gone:

```python
import weakref


def make_handler(large_object):
    ref = weakref.ref(large_object)

    def handle():
        obj = ref()
        if obj is not None:
            ...  # Use the object

    return EventHandler(handle)


subscription = manager.add_event_handler("event", make_handler(large_object))
```

The handler itself stays registered (and cheap) until you remove it.

### Unexpected Handler Execution Order

**Symptoms**: Handlers execute in unexpected order.

**Cause**: Handlers execute in the order they were registered.

**Solution**:

```python
# Handlers execute in registration order
manager.add_event_handler("event", EventHandler(first_handler))  # Executes 1st
manager.add_event_handler("event", EventHandler(second_handler))  # Executes 2nd
manager.add_event_handler("event", EventHandler(third_handler))  # Executes 3rd


# If order matters, register in correct order
# Or use a single handler that calls functions in desired order
def orchestrator():
    first_handler()
    second_handler()
    third_handler()


manager.add_event_handler("event", EventHandler(orchestrator))
```

## Performance Issues

### Slow Event Triggering

**Symptoms**: `trigger_event` takes a long time.

**Possible Causes**:

1. **Too many handlers registered**

   ```python
   # Check number of handlers
   print(f"Manager state: {manager}")


   # Reduce handlers by combining related operations
   def combined_handler():
       operation1()
       operation2()
       operation3()


   manager.add_event_handler("event", EventHandler(combined_handler))
   ```

2. **Handlers performing heavy computation**

   ```python
   # Profile handler execution time
   import time


   def timed_handler():
       start = time.time()
       actual_handler()
       elapsed = time.time() - start
       if elapsed > 0.1:
           print(f"Handler took {elapsed:.2f}s")


   # Move heavy work to background thread
   import concurrent.futures

   executor = concurrent.futures.ThreadPoolExecutor()


   def async_handler():
       executor.submit(heavy_computation)


   manager.add_event_handler("event", EventHandler(async_handler))
   ```

3. **Frequent condition evaluation**

   ```python
   # Use PeriodicCondition to reduce execution frequency
   from minevent import EventHandler, PeriodicCondition

   # Instead of executing every time
   manager.add_event_handler("frequent_event", EventHandler(expensive_handler))

   # Execute less frequently
   manager.add_event_handler(
       "frequent_event",
       EventHandler(expensive_handler, condition=PeriodicCondition(freq=10)),
   )
   ```

## Debugging Techniques

### Enable Logging

```python
import logging

# Enable debug logging for minevent
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("minevent")
logger.setLevel(logging.DEBUG)

# Now minevent will log when handlers are added/removed/triggered
manager = EventManager()
manager.add_event_handler("event", EventHandler(my_handler))
manager.trigger_event("event")
```

### Inspect Event Manager State

```python
# Print the number of handlers of each event
print(manager)

# List the registrations of an event
print(manager.get_subscriptions("my_event"))

# Check if an event has handlers
print("my_event" in manager)
```

### Add Debugging Handlers

```python
# Add a debug handler that logs all events
def debug_handler(event_name):
    print(f"DEBUG: Event '{event_name}' triggered")


# Register for multiple events
for event in ["event1", "event2", "event3"]:
    manager.add_event_handler(event, EventHandler(debug_handler, handler_args=(event,)))
```

## Testing Issues

### Handlers Not Called in Tests

**Cause**: Event manager not properly set up in test fixtures.

**Solution**:

```python
import pytest
from minevent import EventManager, EventHandler


@pytest.fixture
def manager():
    """Create a fresh event manager for each test."""
    mgr = EventManager()
    yield mgr
    mgr.reset()  # Clean up after test


def test_handler_execution(manager):
    """Test that handler is called."""
    called = []

    def test_handler():
        called.append(True)

    manager.add_event_handler("test_event", EventHandler(test_handler))
    manager.trigger_event("test_event")

    assert len(called) == 1
```

### Mocking Handlers

```python
from unittest.mock import Mock


def test_with_mock():
    """Test using mock handlers."""
    manager = EventManager()
    mock_handler = Mock()

    manager.add_event_handler("event", EventHandler(mock_handler))
    manager.trigger_event("event")

    mock_handler.assert_called_once()
```

## Getting Help

If you're still experiencing issues:

1. **Check the FAQ**: See [FAQ](faq.md) for common questions
   2**Search Issues**: Check
   [existing issues](https://github.com/durandtibo/minevent/issues) on GitHub
   3**Ask for Help**: Open a
   [new issue](https://github.com/durandtibo/minevent/issues/new) with:
   - Your `minevent` version
   - Python version
   - Minimal code to reproduce the problem
   - Full error message and stack trace
   - What you've tried so far

## Reporting Bugs

When reporting bugs, please include:

1. **Environment Information**:

   ```python
   import minevent
   import sys

   print(f"minevent version: {minevent.__version__}")
   print(f"Python version: {sys.version}")
   ```

2. **Minimal Reproducible Example**: Simplest code that reproduces the issue

3. **Expected vs Actual Behavior**: What you expected to happen vs what actually happened

4. **Stack Trace**: Full error message if applicable

5. **Steps to Reproduce**: Clear steps to reproduce the issue
