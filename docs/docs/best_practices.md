# Best Practices

This guide provides recommendations for using `minevent` effectively in your projects.

## Event Naming

### Use Clear, Descriptive Names

Event names should clearly describe what happened or will happen:

```python
# Good
manager.trigger_event("training_epoch_completed")
manager.trigger_event("model_checkpoint_saved")
manager.trigger_event("validation_started")

# Less clear
manager.trigger_event("event1")
manager.trigger_event("done")
manager.trigger_event("x")
```

### Use Consistent Naming Conventions

Choose a naming convention and stick to it throughout your project:

```python
# Option 1: Snake case with verb in past tense
"training_started"

"epoch_completed"
"validation_finished"

# Option 2: Namespace-style with present tense
"training.start"
"training.epoch.complete"
"validation.finish"
```

### Use Hierarchical Event Names

For complex systems, use hierarchical naming to organize events:

```python
# Training lifecycle
"training.start"

"training.epoch.start"
"training.batch.start"
"training.batch.end"
"training.epoch.end"
"training.end"

# Model lifecycle
"model.created"
"model.compiled"
"model.saved"
```

## Event Handler Design

### Keep Handlers Focused

Each handler should do one thing well:

```python
# Good: Separate handlers for separate concerns
def log_metrics(metrics):
    logger.info(f"Metrics: {metrics}")


def save_checkpoint(model, epoch):
    torch.save(model.state_dict(), f"checkpoint_epoch_{epoch}.pt")


def update_progress_bar(current, total):
    progress_bar.update(current / total)


# Less ideal: One handler doing multiple things
def do_everything(model, metrics, epoch, current, total):
    logger.info(f"Metrics: {metrics}")
    torch.save(model.state_dict(), f"checkpoint_epoch_{epoch}.pt")
    progress_bar.update(current / total)
```

### Handle Exceptions Gracefully

Protect your main logic from handler failures:

```python
from minevent import EventHandler


def safe_handler(*args, **kwargs):
    try:
        # Your handler logic
        process_data(*args, **kwargs)
    except Exception as e:
        logger.error(f"Handler failed: {e}")
        # Optionally re-raise if critical
        # raise


handler = EventHandler(safe_handler)
```

### Use Type Hints

Make your handlers more maintainable with type hints:

```python
from typing import Dict, Any


def log_metrics(metrics: Dict[str, float], epoch: int) -> None:
    """Log training metrics for the current epoch.

    Args:
        metrics: Dictionary of metric names to values
        epoch: Current training epoch number
    """
    logger.info(f"Epoch {epoch}: {metrics}")


handler = EventHandler(
    log_metrics, handler_kwargs={"metrics": {"loss": 0.5}, "epoch": 1}
)
```

## Event Manager Usage

### Centralize Event Manager Creation

Create the event manager in one place and pass it where needed:

```python
# Good: Create once, pass around
def main():
    manager = EventManager()
    setup_handlers(manager)
    trainer = Trainer(manager)
    trainer.train()


def setup_handlers(manager: EventManager):
    manager.add_event_handler("epoch_end", EventHandler(save_checkpoint))
    manager.add_event_handler("training_end", EventHandler(log_summary))


# Avoid: Global event manager
# MANAGER = EventManager()  # Global state can be problematic
```

### Check Before Adding Duplicate Handlers

Prevent duplicate handler registrations:

```python
# Add handler only if not already present
handler = EventHandler(my_function)
if not manager.has_event_handler(handler, "my_event"):
    manager.add_event_handler("my_event", handler)
```

### Clean Up When Done

Reset or properly dispose of event managers when they're no longer needed:

```python
try:
    # Training loop
    trainer.train(manager)
finally:
    # Clean up
    manager.reset()
```

## Conditional Event Handling

### Use Conditions for Periodic Operations

For operations that shouldn't happen every time:

```python
from minevent import ConditionalEventHandler, PeriodicCondition

# Save checkpoint every 10 epochs
save_handler = ConditionalEventHandler(save_checkpoint, PeriodicCondition(freq=10))
manager.add_event_handler("epoch_end", save_handler)

# Log metrics every 100 batches
log_handler = ConditionalEventHandler(log_batch_metrics, PeriodicCondition(freq=100))
manager.add_event_handler("batch_end", log_handler)
```

## Integration Patterns

### ML Training Pipeline Pattern

```python
class Trainer:
    def __init__(self, model, manager: EventManager):
        self.model = model
        self.manager = manager

    def train(self, epochs: int, train_loader, val_loader):
        self.manager.trigger_event("training_start")

        for epoch in range(epochs):
            self.manager.trigger_event("epoch_start")

            # Training
            train_loss = self._train_epoch(train_loader)
            self.manager.trigger_event("training_epoch_end")

            # Validation
            val_loss = self._validate(val_loader)
            self.manager.trigger_event("validation_epoch_end")

            self.manager.trigger_event("epoch_end")

        self.manager.trigger_event("training_end")

    def _train_epoch(self, train_loader):
        for batch in train_loader:
            self.manager.trigger_event("batch_start")
            loss = self._process_batch(batch)
            self.manager.trigger_event("batch_end")
        return loss
```

### Plugin System Pattern

```python
class PluginManager:
    """Manage plugins using event system."""

    def __init__(self):
        self.event_manager = EventManager()
        self.plugins = []

    def register_plugin(self, plugin):
        """Register a plugin and its event handlers."""
        self.plugins.append(plugin)
        plugin.setup(self.event_manager)

    def trigger(self, event: str, **kwargs):
        """Trigger event with data."""
        # Store kwargs somewhere accessible to handlers
        self.event_manager.trigger_event(event)


# Plugin implementation
class LoggingPlugin:
    def setup(self, manager: EventManager):
        manager.add_event_handler(
            "model_trained", EventHandler(self.log_training_complete)
        )

    def log_training_complete(self):
        print("Training completed!")
```

### Callback System Pattern

```python
class CallbackSystem:
    """Wrap minevent for a cleaner callback API."""

    def __init__(self):
        self._manager = EventManager()

    def on(self, event: str, callback, condition=None):
        """Register a callback for an event."""
        if condition:
            handler = ConditionalEventHandler(callback, condition)
        else:
            handler = EventHandler(callback)
        self._manager.add_event_handler(event, handler)

    def emit(self, event: str):
        """Emit an event."""
        self._manager.trigger_event(event)


# Usage
callbacks = CallbackSystem()
callbacks.on("training_complete", send_notification)
callbacks.on("checkpoint", save_model, condition=PeriodicCondition(freq=10))
```

## Testing

### Test Event Handlers Independently

```python
def test_handler():
    """Test handler logic without event manager."""
    # Arrange
    handler = EventHandler(my_function, handler_args=("test",))

    # Act
    handler.handle()

    # Assert - verify expected behavior
    assert expected_result == actual_result
```

### Mock Event Handlers in Tests

```python
from unittest.mock import Mock


def test_event_system():
    """Test event system with mock handlers."""
    manager = EventManager()
    mock_handler = Mock()

    manager.add_event_handler("test_event", EventHandler(mock_handler))
    manager.trigger_event("test_event")

    mock_handler.assert_called_once()
```

### Test Event Flow

```python
def test_training_events():
    """Test that training triggers expected events."""
    manager = EventManager()
    events_triggered = []

    def track_event(event_name):
        events_triggered.append(event_name)

    manager.add_event_handler("start", EventHandler(track_event, ("start",)))
    manager.add_event_handler("end", EventHandler(track_event, ("end",)))

    # Simulate training
    manager.trigger_event("start")
    manager.trigger_event("end")

    assert events_triggered == ["start", "end"]
```

## Performance Considerations

### Minimize Handler Count

Too many handlers can slow down event triggering:

```python
# Good: One handler for related operations
def batch_operations(batch):
    log_batch(batch)
    update_metrics(batch)
    check_conditions(batch)


manager.add_event_handler("batch_end", EventHandler(batch_operations))

# Less efficient: Multiple handlers for small operations
# manager.add_event_handler("batch_end", EventHandler(log_batch))
# manager.add_event_handler("batch_end", EventHandler(update_metrics))
# manager.add_event_handler("batch_end", EventHandler(check_conditions))
```

### Use Conditional Handlers for Infrequent Operations

Don't execute expensive operations every time:

```python
# Good: Only save checkpoint periodically
manager.add_event_handler(
    "epoch_end", ConditionalEventHandler(save_checkpoint, PeriodicCondition(freq=10))
)

# Less efficient: Save every epoch when not needed
# manager.add_event_handler("epoch_end", EventHandler(save_checkpoint))
```

### Profile Handler Performance

Identify slow handlers:

```python
import time


def profiled_handler(*args, **kwargs):
    start = time.time()
    actual_handler(*args, **kwargs)
    elapsed = time.time() - start
    if elapsed > 0.1:  # Log if takes more than 100ms
        logger.warning(f"Handler took {elapsed:.2f}s")
```

## Common Pitfalls

### Avoid Modifying State During Event Triggering

```python
# Problematic: Removing handlers during event triggering
def problematic_handler(manager, event, handler):
    # This can cause issues if called during event triggering
    manager.remove_event_handler(event, handler)


# Better: Flag for removal, clean up later
handlers_to_remove = []


def safe_handler(event, handler):
    handlers_to_remove.append((event, handler))


# Clean up after event triggering is complete
for event, handler in handlers_to_remove:
    manager.remove_event_handler(event, handler)
```

### Don't Rely on Execution Order Across Events

```python
# Problematic: Assuming event order
manager.trigger_event("event1")
manager.trigger_event("event2")
# Handlers for event1 and event2 may have side effects,
# but don't assume event1 handlers complete before event2 triggers

# Better: Use explicit ordering within the same event
manager.add_event_handler("event", EventHandler(step1))
manager.add_event_handler("event", EventHandler(step2))  # Runs after step1
```

### Avoid Circular Event Triggering

```python
# Problematic: Handler triggers the same event
def recursive_handler(manager):
    manager.trigger_event("my_event")  # This creates infinite recursion!


# Better: Use different events or add guards
def safe_handler(manager, depth=0):
    if depth > 0:
        return
    # Do work
    manager.trigger_event("next_event")
```
