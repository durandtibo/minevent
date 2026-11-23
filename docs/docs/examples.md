# Examples

This page shows how to use `minevent` in practical situations. Every example runs as written: the
[quickstart](quickstart.md) explains the API step by step, and the [user guide](guide.md) lists the
recommendations.

## Add logging to a training loop

The training loop triggers events and knows nothing about the handlers. The caller decides what
happens, so logging, checkpointing or monitoring is added without changing the loop:

```pycon
>>> from minevent import EventManager
>>> def train(manager: EventManager, epochs: int) -> None:
...     manager.trigger_event("training_start")
...     for epoch in range(epochs):
...         loss = 1.0 / (epoch + 1)
...         manager.trigger_event("epoch_end", epoch=epoch, loss=loss)
...     manager.trigger_event("training_end")
...
>>> manager = EventManager()
>>> train(manager, epochs=2)
>>> _ = manager.add_event_handler("training_start", lambda: print("Training started"))
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda epoch, loss: print(f"epoch {epoch}: loss={loss}")
... )
>>> _ = manager.add_event_handler("training_end", lambda: print("Training ended"))
>>> train(manager, epochs=2)
Training started
epoch 0: loss=1.0
epoch 1: loss=0.5
Training ended

```

The first call of `train` prints nothing because no handler is registered.

## Run a handler every N epochs

Give the registration a condition. `PeriodicCondition(freq=3)` is `True` on the first call and then
every three calls; `skip_first=True` skips the first call:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda epoch: print(f"checkpoint at epoch {epoch}"),
...     condition=PeriodicCondition(freq=3, skip_first=True),
... )
>>> for epoch in range(7):
...     manager.trigger_event("epoch_end", epoch=epoch)
checkpoint at epoch 3
checkpoint at epoch 6

```

`AfterNCondition(n)` is `False` for the first `n` calls, which is useful for a warm-up:

```pycon
>>> from minevent import AfterNCondition, EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda epoch: print(f"validate at epoch {epoch}"), condition=AfterNCondition(2)
... )
>>> for epoch in range(4):
...     manager.trigger_event("epoch_end", epoch=epoch)
validate at epoch 2
validate at epoch 3

```

## Write a custom condition

A condition is any function without argument that returns a boolean. A class with `__call__` is
useful when the condition has a state or reads another object:

```pycon
>>> from minevent import EventManager
>>> class Flag:
...     def __init__(self) -> None:
...         self.enabled = False
...     def __call__(self) -> bool:
...         return self.enabled
...
>>> verbose = Flag()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("batch_end", lambda: print("batch done"), condition=verbose)
>>> manager.trigger_event("batch_end")
>>> verbose.enabled = True
>>> manager.trigger_event("batch_end")
batch done

```

To combine conditions, write a function, for example `condition=lambda: a() and b()`.

## Keep a state in a handler

A class with a `__call__(self, **payload)` method is a handler with its own state. This one
collects the losses and is read after the training:

```pycon
>>> from minevent import EventManager
>>> class LossHistory:
...     def __init__(self) -> None:
...         self.losses = []
...     def __call__(self, loss: float, **kwargs) -> None:
...         self.losses.append(loss)
...
>>> history = LossHistory()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", history)
>>> for epoch, loss in enumerate([0.9, 0.6, 0.4]):
...     manager.trigger_event("epoch_end", epoch=epoch, loss=loss)
>>> history.losses
[0.9, 0.6, 0.4]

```

The `**kwargs` accepts the payload keys that the handler does not use. Another way is
`filter_payload=True`, which passes only the keys of the signature.

## Share an event between handlers with different needs

With `filter_payload=True`, each handler receives only the payload keys that it accepts, so
handlers do not need `**kwargs`:

```pycon
>>> from minevent import EventManager
>>> def log_loss(loss: float) -> None:
...     print(f"loss {loss}")
...
>>> def log_epoch(epoch: int) -> None:
...     print(f"epoch {epoch}")
...
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_loss, filter_payload=True)
>>> _ = manager.add_event_handler("epoch_end", log_epoch, filter_payload=True)
>>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
loss 0.5
epoch 3

```

## Register with a decorator

`on` registers a function and returns it unchanged, so the function can still be called directly. It
takes the same options as `add_event_handler`:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> @manager.on("epoch_end", condition=PeriodicCondition(freq=2), filter_payload=True)
... def log_epoch(epoch: int) -> None:
...     print(f"epoch {epoch}")
...
>>> for epoch in range(3):
...     manager.trigger_event("epoch_end", epoch=epoch)
epoch 0
epoch 2
>>> log_epoch(10)
epoch 10

```

## Bind fixed arguments

Use `functools.partial` for the arguments that do not come from the payload:

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def save(path: str, epoch: int) -> None:
...     print(f"save epoch {epoch} to {path}")
...
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", functools.partial(save, "model.pt"))
>>> manager.trigger_event("epoch_end", epoch=4)
save epoch 4 to model.pt

```

## Run a handler once

`once=True` removes the registration just before its handler runs. With a condition, it waits for
the first trigger where the condition is `True`:

```pycon
>>> from minevent import AfterNCondition, EventManager
>>> manager = EventManager()
>>> subscription = manager.add_event_handler(
...     "epoch_end", lambda: print("saved"), once=True, condition=AfterNCondition(2)
... )
>>> for _ in range(4):
...     manager.trigger_event("epoch_end")
saved
>>> subscription.active
False

```

## Remove a handler

Keep the `Subscription` returned by `add_event_handler` to remove exactly that registration. A
`with` block removes it when the block exits, which suits a handler that lives for one phase of the
program:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> with manager.add_event_handler("batch_end", lambda: print("profiling")):
...     manager.trigger_event("batch_end")
profiling
>>> manager.trigger_event("batch_end")
>>> len(manager)
0

```

`manager.clear_event("batch_end")` removes all the handlers of an event, and `manager.reset()`
removes all the handlers of all the events.

## Write a plugin

A plugin registers its handlers when it is set up, and keeps the subscriptions to remove them when
it is torn down:

```pycon
>>> from minevent import EventManager
>>> class ProgressPlugin:
...     def setup(self, manager: EventManager) -> None:
...         self.subscriptions = [
...             manager.add_event_handler("epoch_start", self.on_epoch_start),
...             manager.add_event_handler("epoch_end", self.on_epoch_end),
...         ]
...     def teardown(self) -> None:
...         for subscription in self.subscriptions:
...             subscription.remove()
...     def on_epoch_start(self, epoch: int) -> None:
...         print(f"start {epoch}")
...     def on_epoch_end(self, epoch: int) -> None:
...         print(f"end {epoch}")
...
>>> manager = EventManager()
>>> plugin = ProgressPlugin()
>>> plugin.setup(manager)
>>> manager.trigger_event("epoch_start", epoch=0)
start 0
>>> manager.trigger_event("epoch_end", epoch=0)
end 0
>>> plugin.teardown()
>>> len(manager)
0

```

## Use coroutine handlers

`atrigger_event` awaits the coroutine handlers and also runs the synchronous ones, one after the
other, in the registration order. `trigger_event` raises a `TypeError` for a coroutine handler:

```pycon
>>> import asyncio
>>> from minevent import EventManager
>>> async def notify(epoch: int) -> None:
...     await asyncio.sleep(0)
...     print(f"notified epoch {epoch}")
...
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", lambda epoch: print(f"epoch {epoch}"))
>>> _ = manager.add_event_handler("epoch_end", notify)
>>> asyncio.run(manager.atrigger_event("epoch_end", epoch=1))
epoch 1
notified epoch 1

```

## Handle the errors of a handler

A handler that raises stops the dispatch, and the exception reaches the caller with a note that
names the event and the handler:

```pycon
>>> from minevent import EventManager
>>> def fail() -> None:
...     raise ValueError("boom")
...
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", fail)
>>> _ = manager.add_event_handler("my_event", lambda: print("not reached"))
>>> try:
...     manager.trigger_event("my_event")
... except ValueError as exc:
...     print(exc, "|", exc.__notes__[0])
boom | raised by fail while handling the event 'my_event'

```

To keep the other handlers running, catch the exception in the handler.

## Test a handler

A handler is a plain callable, so test it without a manager. Test the wiring with a mock:

```python
from unittest.mock import Mock

from minevent import EventManager


def test_epoch_end_calls_the_handler():
    manager = EventManager()
    handler = Mock()
    manager.add_event_handler("epoch_end", handler)
    manager.trigger_event("epoch_end", epoch=1)
    handler.assert_called_once_with(epoch=1)
```
