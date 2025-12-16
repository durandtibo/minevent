# Troubleshooting

This guide helps you diagnose and resolve common issues when using `minevent`.

## Common Issues

### Event Handler Not Executing

**Symptoms**: You trigger an event but the handler doesn't execute.

**Possible Causes and Solutions**:

1. **Handler not registered**

   ```python
   # Check if handler is registered
   handler = EventHandler(my_function)
   if not manager.has_event_handler(handler, "my_event"):
       print("Handler not registered!")
       manager.add_event_handler("my_event", handler)
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
   handler = ConditionalEventHandler(my_function, condition)

   # The handler only executes every 5 calls
   for i in range(10):
       manager.trigger_event("my_event")
       print(f"Call {i}: Condition evaluated to {condition.evaluate()}")
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

### RuntimeError: Event Does Not Exist

**Symptoms**: `RuntimeError: 'event_name' event does not exist` when trying to remove a handler.

**Cause**: You're trying to remove a handler from an event that has no registered handlers.

**Solution**:

```python
# Check if event has handlers before removing
if manager.has_event_handler(handler):
    try:
        manager.remove_event_handler("my_event", handler)
    except RuntimeError as e:
        print(f"Could not remove handler: {e}")
```

### RuntimeError: Handler Not Found

**Symptoms**: Error when trying to remove a handler that doesn't exist for that event.

**Cause**: The handler was never added, or it was already removed.

**Solution**:

```python
# Verify handler exists before removal
handler = EventHandler(my_function)
if manager.has_event_handler(handler, "my_event"):
    manager.remove_event_handler("my_event", handler)
else:
    print("Handler not registered for this event")
```

### Handler Comparison Issues

**Symptoms**: `has_event_handler` returns `False` even though you added the handler.

**Cause**: Handler comparison uses the `equal` method, which compares handler functions and
arguments.

**Solution**:

```python
# These are considered DIFFERENT handlers
handler1 = EventHandler(my_function, handler_args=(1,))
handler2 = EventHandler(my_function, handler_args=(2,))  # Different args
print(handler1.equal(handler2))  # False

# These are considered EQUAL
handler3 = EventHandler(my_function, handler_args=(1,))
handler4 = EventHandler(my_function, handler_args=(1,))  # Same args
print(handler3.equal(handler4))  # True

# Solution: Keep reference to original handler
original_handler = EventHandler(my_function, handler_args=(1,))
manager.add_event_handler("event", original_handler)
# Later...
manager.has_event_handler(original_handler, "event")  # True
```

### Memory Leaks

**Symptoms**: Memory usage grows over time in long-running applications.

**Cause**: Event handlers holding references to large objects or not being cleaned up.

**Solution**:

```python
# Clear handlers when done
def cleanup():
    manager.reset()  # Removes all handlers


# Use weak references for large objects
import weakref


class MyHandler:
    def __init__(self, large_object):
        self._large_object_ref = weakref.ref(large_object)

    def handle(self):
        obj = self._large_object_ref()
        if obj is not None:
            # Use object
            pass
```

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
   from minevent import ConditionalEventHandler, PeriodicCondition

   # Instead of executing every time
   manager.add_event_handler("frequent_event", EventHandler(expensive_handler))

   # Execute less frequently
   manager.add_event_handler(
       "frequent_event",
       ConditionalEventHandler(expensive_handler, PeriodicCondition(freq=10)),
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
# Print manager state to see all registered handlers
print(manager)

# Check last triggered event
print(f"Last event: {manager.last_triggered_event}")

# Check if specific handler is registered
handler = EventHandler(my_function)
print(f"Handler registered: {manager.has_event_handler(handler)}")
print(f"Handler registered for 'event': {manager.has_event_handler(handler, 'event')}")
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
