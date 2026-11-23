# User guide

This guide collects the recommendations, the patterns and the troubleshooting tips for using
`minevent`. The [quickstart](quickstart.md) explains the API step by step, and the
[architecture](architecture.md) page lists the guarantees of the library.

## Events

An event is a case-sensitive `str`. Any other type raises a `TypeError`.

- Name the event after what happened, in the past tense: `epoch_end`, `checkpoint_saved`, not
  `event1` or `done`.
- Pick one convention for the whole project, for example `snake_case` (`batch_end`) or a namespace
  (`training.batch.end`). Names are only strings, so `minevent` has no notion of hierarchy.
- Define the names in one place (constants or an `Enum` with `str` values) to avoid typos: the
  events `"epoch_end"` and `"epoch-end"` are different, and triggering an event without handler does
  nothing.

## Event handlers

### Keep handlers focused

One handler does one thing (log, save, update a progress bar). Handlers of an event run in the order
they were registered, so register them in the order they must run.

### Pass the data as a payload

The keyword arguments of `trigger_event` are passed to every handler:

```pycon
>>> from minevent import EventManager
>>> def log_epoch(epoch: int, loss: float) -> None:
...     print(f"epoch {epoch}: {loss}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
epoch 3: 0.5

```

Every handler of the event receives the whole payload, and a handler that does not accept a key
raises a `TypeError`. Use `filter_payload=True` to give each handler only the keys of its signature,
so handlers with different needs can share an event:

```pycon
>>> from minevent import EventManager
>>> def log_epoch(epoch: int) -> None:
...     print(f"epoch {epoch}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch, filter_payload=True)
>>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
epoch 3

```

Bind the arguments that do not come from the payload with `functools.partial`. A payload key that
repeats a keyword bound by the partial overrides it, as it does for any call of a partial.

### Handle the exceptions

Handlers run fail-fast: if a handler raises, the exception reaches the caller of `trigger_event` and
the next handlers of the event do not run. The exception is the original one, with a note that
names the event and the function of the handler (never its arguments):

```pycon
>>> from minevent import EventManager
>>> def fail() -> None:
...     raise ValueError("boom")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", fail)
>>> try:
...     manager.trigger_event("my_event")
... except ValueError as exc:
...     print(exc.__notes__[0])
raised by fail while handling the event 'my_event'

```

If the failure of a handler must not stop the training, catch the exception in the handler. There is
no option to collect the errors of all the handlers (see the non-goals in the architecture page).

### Async handlers

`trigger_event` is synchronous. A handler that returns an awaitable (a coroutine function) raises a
`TypeError` there, instead of silently dropping the coroutine. Use `atrigger_event` to await the
handlers, one after the other, in the registration order. Synchronous handlers can be mixed with
coroutine handlers, and they block the event loop while they run.

## Conditions

A condition is a function without argument that returns a boolean. It is called each time the event
is triggered, before the handler, and the handler runs only if it returns `True`:

```python
from minevent import PeriodicCondition

# Save a checkpoint every 10 epochs, and log every 100 batches
manager.add_event_handler("epoch_end", save_checkpoint, condition=PeriodicCondition(freq=10))
manager.add_event_handler("batch_end", log_batch, condition=PeriodicCondition(freq=100))

# Any function works as a condition
manager.add_event_handler("epoch_end", notify, condition=lambda: is_main_process)
```

- `PeriodicCondition` and `AfterNCondition` keep a counter. Do not share one
  instance between two handlers: they would advance the same counter. Create one per handler.
  Call `reset()` to restart the counter.
- To combine conditions, write a function. `lambda: a() and b()` skips `b` when `a` is `False`;
  `lambda: all([a(), b()])` evaluates both, so stateful conditions advance together.
- A stateful condition is not protected by a lock: call it from one thread.

## The event manager

### Create it in one place

Create the manager once and pass it where it is needed. `minevent` has no global manager on
purpose: it keeps the tests independent and makes the ownership clear.

```python
def main():
    manager = EventManager()
    setup_handlers(manager)
    Trainer(manager).train()


def setup_handlers(manager: EventManager) -> None:
    manager.add_event_handler("epoch_end", save_checkpoint)
    manager.add_event_handler("training_end", log_summary)
```

A manager is always truthy, even when it is empty, so `manager or EventManager()` keeps the manager
you pass; use `len(manager)` for the number of registrations. A manager cannot be copied or pickled
(`copy.copy`, `copy.deepcopy` and `pickle` raise a `TypeError`): create a new one.

### Register any callable

`add_event_handler` accepts any callable, called as `handler(**payload)`: a function, a method, a
callable object or a `functools.partial`. The options of the registration are its keyword-only
arguments: `once`, `condition` and `filter_payload`. Use `functools.partial` to bind the arguments
that do not come from the payload.

```pycon
>>> import functools
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(print, "Hello!"))
>>> manager.trigger_event("my_event")
Hello!
>>> def log_epoch(epoch):
...     print(f"epoch {epoch}")
...
>>> _ = manager.add_event_handler(
...     "epoch_end", log_epoch, condition=PeriodicCondition(freq=2), filter_payload=True
... )
>>> manager.trigger_event("epoch_end", epoch=1, loss=0.5)
epoch 1
>>> manager.trigger_event("epoch_end", epoch=2, loss=0.4)

```

With `filter_payload=True`, the signature of a `functools.partial` does not contain the positional
arguments it binds, so a payload key with the same name is dropped. A payload key that repeats a
keyword bound by the partial overrides it.

### Keep the subscription

`add_event_handler` returns a `Subscription`, the registration of the handler. It is the only way to
identify a registration: the same callable can be registered several times, and each registration is
a different `Subscription`.

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("my_event", print)
>>> subscription.active
True
>>> subscription.remove()
True
>>> subscription.remove()
False

```

- `remove()` removes that registration only, once. It returns `False` if the registration is already
  gone (removed, or cleared by `clear_event` or `reset`, or consumed by `once=True`).
- `with manager.add_event_handler(...):` removes the registration when the block exits, which is
  convenient for a profiler or a progress bar that lives for one phase of the program.
- `manager.get_subscriptions(event)` lists the registrations of an event if you did not keep them,
  and `subscription.handler` gives the handler.
- `@manager.on("event")` registers a function as a handler and returns it unchanged. It takes
  `once`, `condition` and `filter_payload`, as in `@manager.on("epoch_end", filter_payload=True)`,
  which are also the keyword-only arguments of `add_event_handler`. Use `add_event_handler` if you
  need the `Subscription`.
- `once=True` removes the registration at the next trigger of the event, even if the condition of the
  handler is `False`. To wait for the first time the condition is `True`, see the quickstart.

### Avoid duplicates

Registering the same handler twice runs it twice. To register it once, look at the registrations:

```python
if not any(sub.handler is handler for sub in manager.get_subscriptions("my_event")):
    manager.add_event_handler("my_event", handler)
```

### Clean up

A registered handler lives as long as the manager: `obj.method` keeps `obj` alive, and so do the
arguments bound by a `functools.partial` and closures. `minevent` uses no weak reference. Remove the
subscriptions of the objects you no longer need, use a `with` block, or call `clear_event` /
`reset`:

```python
try:
    trainer.train(manager)
finally:
    manager.reset()
```

## Integration patterns

### Training loop

```python
class Trainer:
    def __init__(self, model, manager: EventManager) -> None:
        self.model = model
        self.manager = manager

    def train(self, epochs: int, loader) -> None:
        self.manager.trigger_event("training_start")
        for epoch in range(epochs):
            self.manager.trigger_event("epoch_start", epoch=epoch)
            for batch in loader:
                loss = self.step(batch)
                self.manager.trigger_event("batch_end", epoch=epoch, loss=loss)
            self.manager.trigger_event("epoch_end", epoch=epoch)
        self.manager.trigger_event("training_end")
```

### Plugins

A plugin registers its own handlers, and keeps the subscriptions to unregister them:

```python
class LoggingPlugin:
    def setup(self, manager: EventManager) -> None:
        self.subscription = manager.add_event_handler(
            "training_end", self.log_training_complete
        )

    def teardown(self) -> None:
        self.subscription.remove()

    def log_training_complete(self) -> None:
        print("Training completed!")
```

### Custom handlers and conditions

Write a class with a `__call__(self, **payload)` method for a handler with its own state (use
`async def __call__` for a coroutine). A condition is any class with a `__call__(self) -> bool`
method.

## Testing

Test a handler without a manager, and the wiring with a mock:

```python
from unittest.mock import Mock


def test_epoch_end_calls_handler():
    manager = EventManager()
    mock = Mock()
    manager.add_event_handler("epoch_end", mock)
    manager.trigger_event("epoch_end", epoch=1)
    mock.assert_called_once_with(epoch=1)


def test_handler_directly():
    handler = functools.partial(print, "test")
    handler()
```

Use a new `EventManager` in each test, and `manager.reset()` if the manager is shared.

## Performance

`import minevent` is cheap: it imports the standard library modules `threading`, `functools`,
`collections.abc` and `typing` only, and not `logging`, `inspect`, `asyncio` or
`importlib.metadata` (`inspect` is imported when `filter_payload=True` is used, and
`importlib.metadata` when `__version__` is read). It takes a few milliseconds, so a script can import
it without a measurable cost.

The cost of `trigger_event` is the cost of the handlers: about 0.4 µs for a manager with one trivial
handler, and about 0.1 µs for each additional handler on a laptop. A condition avoids the work of
an expensive handler (`PeriodicCondition`). To find a slow handler, time it or wrap it (see [Debug](#debug)).

A handler that is slow blocks the caller. Hand the work to an executor in the handler if the caller
must not wait.

## Pitfalls

- **A handler that retriggers its own event** recurses until `RecursionError`. Use a different event
  or a flag.
- **A handler removed during a trigger still runs in that trigger.** The registrations that exist
  when the trigger starts are run. Handlers added during a trigger run at the next trigger.
  A `once` registration removed by an earlier handler of the same trigger does not run.
- **The payload is shared**: all handlers get the same objects. A handler that mutates a payload
  object is seen by the next handlers.
- **Threads**: the registry is thread-safe, the handlers run in the thread that triggers the event,
  concurrently if several threads trigger it. A handler that shares state must protect it.

## Troubleshooting

### My handler does not run

1. The handler is registered for that event: `manager.get_subscriptions("my_event")`.
2. The event name matches exactly (case-sensitive).
3. The condition returns `True` (a `PeriodicCondition(freq=5)` skips four calls out of five).
4. It was not registered with `once=True` and already consumed: `subscription.active` is `False`.
5. A handler of the same event ahead of it raised: the next handlers are skipped.

### `TypeError: ... got an unexpected keyword argument`

The payload is given to every handler. Accept `**kwargs` or use `filter_payload=True`.

### `TypeError: ... returned an awaitable; use atrigger_event`

The handler is a coroutine function (a coroutine object is closed, so Python does not warn that it
was never awaited). Call `await manager.atrigger_event(...)`.

### `subscription.remove()` returns `False`

The registration is already removed. This is not an error: `remove()` is idempotent.

### Debug

- `print(manager)` shows the number of handlers of each event, and `manager.get_subscriptions(e)`
  the registrations.
- `minevent` does not log. Wrap a handler to trace it (the wrapper is a plain callable):

  ```python
  def traced(handler):
      def wrapper(**payload):
          print(f"calling {handler.__qualname__}")
          return handler(**payload)

      return wrapper


  manager.add_event_handler("batch_end", traced(log_batch))
  ```

- Register a handler that prints the payload while you investigate:

  ```python
  manager.add_event_handler("batch_end", lambda **payload: print(payload))
  ```
