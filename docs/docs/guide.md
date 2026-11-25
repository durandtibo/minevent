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

The keyword arguments of `trigger_event` are copied into a read-only `Context`, which is built once
per trigger and passed to every handler that has a parameter:

```pycon
>>> from minevent import Context, EventManager
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}: {context['loss']}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
epoch 3: 0.5

```

A `Context` is a read-only mapping from `str` to values: a handler cannot change what the next
handler sees (the values are not copied, so a mutable value stays mutable). Each handler reads the
keys it needs and decides what to do when one is missing, so handlers with different needs share an
event and an extra key never breaks a handler:

- `context["loss"]` reads a required value and raises a `KeyError` that lists the available keys.
- `context.get("loss", 0.0)` reads an optional value.
- `"loss" in context`, `len(context)`, `context.items()` and `dict(context)` work as for a mapping.

```pycon
>>> from minevent import Context, EventManager
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}, loss {context.get('loss', 'unknown')}")
>>> def say_hello() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> _ = manager.add_event_handler("epoch_end", say_hello)
>>> manager.trigger_event("epoch_end", epoch=3)
epoch 3, loss unknown
Hello!

```

A handler that has a parameter that accepts a positional argument (or a `*args`) is called as
`handler(context)`, and a handler without parameter is called as `handler()`. This is decided once,
when the handler is registered, from the number of parameters: the names are never matched. A
callable whose signature cannot be inspected is called as `handler(context)`.

Bind the arguments that do not come from the payload with `functools.partial`: the context is passed
after the bound positional arguments.

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

`add_event_handler` accepts any callable, called as `handler(context)` or `handler()` (see
[Pass the data as a payload](#pass-the-data-as-a-payload)): a function, a method, a callable object
or a `functools.partial`. The options of the registration are its keyword-only arguments: `once`
and `condition`. Use `functools.partial` to bind the arguments that do not come from the payload.

```pycon
>>> import functools
>>> from minevent import Context, EventManager, PeriodicCondition
>>> def greet(name: str) -> None:
...     print(f"Hello {name}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(greet, "Bob"))
>>> manager.trigger_event("my_event")
Hello Bob!
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}")
>>> _ = manager.add_event_handler(
...     "epoch_end", log_epoch, condition=PeriodicCondition(freq=2)
... )
>>> manager.trigger_event("epoch_end", epoch=1, loss=0.5)
epoch 1
>>> manager.trigger_event("epoch_end", epoch=2, loss=0.4)

```

The signature of a `functools.partial` does not contain the arguments that it binds: a partial that
binds the only positional parameter of a function is called as `handler()`.

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
  `once` and `condition`, as in `@manager.on("epoch_end", once=True)`, which are also the
  keyword-only arguments of `add_event_handler`. Use `add_event_handler` if you
  need the `Subscription`.
- `once=True` runs the handler the first time its condition is `True` (at the next trigger if it has
  no condition), then removes the registration. A condition that is `False` does not consume it.

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
        self.subscription = manager.add_event_handler("training_end", self.log_training_complete)

    def teardown(self) -> None:
        self.subscription.remove()

    def log_training_complete(self) -> None:
        print("Training completed!")
```

### Custom handlers and conditions

Write a class with a `__call__(self, context)` method for a handler with its own state (use
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
    mock.assert_called_once_with({"epoch": 1})


def test_handler_directly():
    handler = functools.partial(print, "test")
    handler()
```

Use a new `EventManager` in each test, and `manager.reset()` if the manager is shared.

## Performance

`import minevent` is cheap: it imports the standard library modules `threading`, `functools`,
`collections.abc` and `typing` only, and not `logging`, `inspect`, `asyncio` or
`importlib.metadata` (`inspect` is imported when the first handler is registered, and
`importlib.metadata` when `__version__` is read). It creates no `typing` object (`Protocol`,
`NamedTuple`, `TypeVar`). It takes a few milliseconds, so a script can import it without a
measurable cost.

The cost of `trigger_event` is the cost of the handlers: about 0.65 µs for a manager with one trivial
handler (it builds one `Context`), and about 0.1 µs for each additional handler on a laptop. A
condition avoids the work of an expensive handler (`PeriodicCondition`). To find a slow handler,
time it or wrap it (see [Debug](#debug)).

A handler that is slow blocks the caller. Hand the work to an executor in the handler if the caller
must not wait.

## Pitfalls

- **A handler that retriggers its own event** recurses until `RecursionError`. Use a different event
  or a flag.
- **A handler added during a trigger runs at the next trigger.** The registrations that exist when
  the trigger starts are visited. A registration removed before its turn does not run, whatever
  removes it (`remove()`, `clear_event`, `reset`). A `remove()` from another thread cannot stop a
  handler that the trigger is about to call.
- **The payload is shared**: all handlers get the same `Context`, which is read-only, and the same
  value objects. A handler that mutates a mutable value (a list, for example) is seen by the next
  handlers.
- **Threads**: the registry is thread-safe, the handlers run in the thread that triggers the event,
  concurrently if several threads trigger it. A handler that shares state must protect it.

## Troubleshooting

### My handler does not run

1. The handler is registered for that event: `manager.get_subscriptions("my_event")`.
2. The event name matches exactly (case-sensitive).
3. The condition returns `True` (a `PeriodicCondition(freq=5)` skips four calls out of five).
4. It was not registered with `once=True` and already consumed: `subscription.active` is `False`.
5. A handler of the same event ahead of it raised: the next handlers are skipped.

### `KeyError: "key 'epoch' not found in the context; ..."`

The trigger did not give the key that the handler requires. The message lists the available keys.
Read an optional value with `context.get("epoch", default)`, or check `"epoch" in context`.

### `TypeError: ... takes 0 positional arguments but 1 was given`

The handler has no parameter that accepts the context, but its signature cannot be inspected, so it
is called as `handler(context)`. Wrap it in a function without parameter, or in a function that
takes the context.

### `TypeError: ... returned an awaitable; use atrigger_event`

The handler is a coroutine function (a coroutine object is closed, so Python does not warn that it
was never awaited). Call `await manager.atrigger_event(...)`.

### `subscription.remove()` returns `False`

The registration is already removed. This is not an error: `remove()` is idempotent.

### Debug

- `print(manager)` shows the number of handlers of each event, and `manager.get_subscriptions(e)`
  the registrations; each one prints its event and the name of its handler
  (`Subscription(event='my_event', handler='print')`).
- `minevent` does not log. Wrap a handler to trace it (the wrapper is a plain callable):

  ```python
  import functools


  def traced(handler):
      @functools.wraps(handler)  # the signature of the handler decides if it gets the context
      def wrapper(*args):
          print(f"calling {handler.__qualname__}")
          return handler(*args)

      return wrapper


  manager.add_event_handler("batch_end", traced(log_batch))
  ```

- Register a handler that prints the payload while you investigate:

  ```python
  manager.add_event_handler("batch_end", lambda context: print(dict(context)))
  ```
