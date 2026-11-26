# Examples

This page shows how to use `minevent` in practical situations. The `pycon` examples run as written.
The [quickstart](quickstart.md) shows each feature on its own, the [user guide](guide.md) lists the
recommendations and the [how it works page](architecture.md) states the rules.

## Add logging to a training loop

The training loop triggers events and knows nothing about the handlers. The caller decides what
happens, so logging, checkpointing or monitoring is added without changing the loop:

```pycon
>>> from minevent import EventManager
>>> def train(manager: EventManager, epochs: int) -> None:
...     manager.trigger_event("training_start")
...     for epoch in range(epochs):
...         loss = 1.0 / (epoch + 1)
...         manager.trigger_event("epoch_end", {"epoch": epoch, "loss": loss})
...     manager.trigger_event("training_end")
>>> manager = EventManager()
>>> train(manager, epochs=2)
>>> _ = manager.add_event_handler("training_start", lambda _: print("Training started"))
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda context: print(f"epoch {context['epoch']}: loss={context['loss']}")
... )
>>> _ = manager.add_event_handler("training_end", lambda _: print("Training ended"))
>>> train(manager, epochs=2)
Training started
epoch 0: loss=1.0
epoch 1: loss=0.5
Training ended

```

The first call of `train` prints nothing because no handler is registered.

## Run a handler every N epochs

Give the registration a condition. `PeriodicCondition(freq=3)` is `True` on the first call and then
every three calls. `start` is the index (from 0) of the first call that is `True`: `start=3` skips
the first call:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"checkpoint at epoch {context['epoch']}"),
...     condition=PeriodicCondition(freq=3, start=3),
... )
>>> for epoch in range(7):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
checkpoint at epoch 3
checkpoint at epoch 6

```

With the epochs counted from 0, `start=2` runs the handler at the end of every third epoch:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"evaluate at epoch {context['epoch']}"),
...     condition=PeriodicCondition(freq=3, start=2),
... )
>>> for epoch in range(7):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
evaluate at epoch 2
evaluate at epoch 5

```

With `freq=1`, the condition is `False` for the first `start` calls, then always `True`, which is
useful for a warm-up:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"validate at epoch {context['epoch']}"),
...     condition=PeriodicCondition(freq=1, start=2),
... )
>>> for epoch in range(4):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
validate at epoch 2
validate at epoch 3

```

## Write a custom condition

A class with `__call__` is useful when a condition has a state or reads another object:

```pycon
>>> from minevent import Context, EventManager
>>> class Flag:
...     def __init__(self) -> None:
...         self.enabled = False
...
...     def __call__(self, _: Context) -> bool:
...         return self.enabled
>>> verbose = Flag()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("batch_end", lambda _: print("batch done"), condition=verbose)
>>> manager.trigger_event("batch_end")
>>> verbose.enabled = True
>>> manager.trigger_event("batch_end")
batch done

```

## Restart a condition

`reset()` restarts the counter of a `PeriodicCondition`, for example at the start of a new training:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> warmup = PeriodicCondition(freq=1, start=1)
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", lambda _: print("validate"), condition=warmup)
>>> for _ in range(2):
...     manager.trigger_event("epoch_end")
validate
>>> warmup.reset()
>>> manager.trigger_event("epoch_end")

```

## Combine conditions

Write a function. `all([a(context), b(context)])` evaluates every condition at each call, so
stateful conditions advance together:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> after_one, periodic = PeriodicCondition(freq=1, start=1), PeriodicCondition(freq=2)
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda _: print("validate"),
...     condition=lambda context: all([after_one(context), periodic(context)]),
... )
>>> for _ in range(5):
...     manager.trigger_event("epoch_end")
validate
validate

```

## Use one condition per handler

A stateful condition keeps its counter in the instance, so create one per registration, for example
with a function:

```pycon
>>> import functools
>>> from minevent import Context, EventManager, PeriodicCondition
>>> manager = EventManager()
>>> def say(name: str, _: Context) -> None:
...     print(name)
>>> def register(name: str) -> None:
...     manager.add_event_handler(
...         name, functools.partial(say, name), condition=PeriodicCondition(freq=2)
...     )
>>> register("first")
>>> register("second")
>>> manager.trigger_event("first")
first
>>> manager.trigger_event("second")
second

```

## Decide from the payload

A condition reads the payload of the trigger. A handler and its condition can read
different keys:

```pycon
>>> from minevent import Context, EventManager
>>> def is_improving(context: Context) -> bool:
...     return context.get("loss", 1.0) < 0.5
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"save the model of epoch {context['epoch']}"),
...     condition=is_improving,
... )
>>> for epoch, loss in enumerate([0.9, 0.4, 0.6, 0.3]):
...     manager.trigger_event("epoch_end", {"epoch": epoch, "loss": loss})
save the model of epoch 1
save the model of epoch 3

```

`PeriodicCondition` ignores the payload. To combine it with a condition on the payload, write a
function that calls both:
`condition=lambda context: periodic(context) and is_improving(context)`.

## Keep a state in a handler

A class with a `__call__(self, context)` method is a handler with its own state. This one
collects the losses and is read after the training:

```pycon
>>> from minevent import Context, EventManager
>>> class LossHistory:
...     def __init__(self) -> None:
...         self.losses = []
...
...     def __call__(self, context: Context) -> None:
...         self.losses.append(context["loss"])
>>> history = LossHistory()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", history)
>>> for epoch, loss in enumerate([0.9, 0.6, 0.4]):
...     manager.trigger_event("epoch_end", {"epoch": epoch, "loss": loss})
>>> history.losses
[0.9, 0.6, 0.4]

```

The handler ignores the keys that it does not read, here `epoch`.

## Pass a dict or a Context

A dict is copied and validated at each trigger, while a `Context` is passed as is, so build it once
to reuse it:

```pycon
>>> from minevent import Context, EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda context: print(f"epoch {context['epoch']}, loss {context['loss']}")
... )
>>> manager.trigger_event("epoch_end", {"epoch": 3, "loss": 0.5})
epoch 3, loss 0.5
>>> context = Context({"epoch": 4, "loss": 0.4})
>>> manager.trigger_event("epoch_end", context)
epoch 4, loss 0.4
>>> manager.trigger_event("epoch_end", context)
epoch 4, loss 0.4

```

## Adapt an existing function

A handler is called with the context, so wrap a function that does not take it, such as
`model.train`, in a lambda that ignores it and chooses the arguments. A default saves the value of a
loop variable:

```pycon
>>> from minevent import EventManager
>>> class Model:
...     def train(self, mode: bool = True) -> None:
...         print(f"train mode: {mode}")
>>> model = Model()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_start", lambda _: model.train())
>>> _ = manager.add_event_handler("validation_start", lambda _: model.train(mode=False))
>>> manager.trigger_event("epoch_start", {"epoch": 0})
train mode: True
>>> manager.trigger_event("validation_start")
train mode: False
>>> for i in range(3):
...     _ = manager.add_event_handler("batch_end", lambda _, i=i: print(i))
>>> manager.trigger_event("batch_end")
0
1
2

```

## Keep a snapshot of the payload

The values of a `Context` are not copied. `copy.deepcopy` takes a snapshot that the next handlers
cannot change:

```pycon
>>> import copy
>>> from minevent import EventManager
>>> snapshots = []
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", lambda context: snapshots.append(copy.deepcopy(context)))
>>> _ = manager.add_event_handler("epoch_end", lambda context: context["losses"].append(0.1))
>>> manager.trigger_event("epoch_end", {"losses": [0.5]})
>>> snapshots
[Context({'losses': [0.5]})]

```

## Register a handler only once

Registering the same handler twice runs it twice. Look at the registrations to add it only if it is
not there:

```pycon
>>> from minevent import Context, EventManager
>>> def hello_handler(_: Context) -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> for _ in range(3):
...     if not any(s.handler is hello_handler for s in manager.get_subscriptions("my_event")):
...         _ = manager.add_event_handler("my_event", hello_handler)
>>> manager
EventManager(events={'my_event': 1})

```

## Trace the handlers

Wrap a handler to see its calls. `functools.wraps` keeps the signature, which is checked at
registration:

```pycon
>>> import functools
>>> from minevent import Context, EventManager
>>> def traced(handler):
...     @functools.wraps(handler)
...     def wrapper(*args):
...         print(f"calling {handler.__name__}")
...         return handler(*args)
...
...     return wrapper
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", traced(log_epoch))
>>> _ = manager.add_event_handler("epoch_end", lambda context: print(dict(context)))
>>> manager.trigger_event("epoch_end", {"epoch": 1})
calling log_epoch
epoch 1
{'epoch': 1}

```

## Write a plugin

A plugin registers its handlers when it is set up, and keeps the subscriptions to remove them when
it is torn down:

```pycon
>>> from minevent import Context, EventManager
>>> class ProgressPlugin:
...     def setup(self, manager: EventManager) -> None:
...         self.subscriptions = [
...             manager.add_event_handler("epoch_start", self.on_epoch_start),
...             manager.add_event_handler("epoch_end", self.on_epoch_end),
...         ]
...
...     def teardown(self) -> None:
...         for subscription in self.subscriptions:
...             subscription.remove()
...
...     def on_epoch_start(self, context: Context) -> None:
...         print(f"start {context['epoch']}")
...
...     def on_epoch_end(self, context: Context) -> None:
...         print(f"end {context['epoch']}")
>>> manager = EventManager()
>>> plugin = ProgressPlugin()
>>> plugin.setup(manager)
>>> manager.trigger_event("epoch_start", {"epoch": 0})
start 0
>>> manager.trigger_event("epoch_end", {"epoch": 0})
end 0
>>> plugin.teardown()
>>> manager
EventManager(events={})

```

## Trigger events from several threads

The manager can be shared between threads. The handlers run in the thread that triggers the event,
possibly at the same time, so a handler protects the state that it shares:

```pycon
>>> import threading
>>> from minevent import Context, EventManager
>>> total, lock = [0], threading.Lock()
>>> def add(context: Context) -> None:
...     with lock:
...         total[0] += context["value"]
>>> manager = EventManager()
>>> _ = manager.add_event_handler("item_done", add)
>>> threads = [
...     threading.Thread(target=manager.trigger_event, args=("item_done", {"value": i}))
...     for i in range(10)
... ]
>>> for thread in threads:
...     thread.start()
>>> for thread in threads:
...     thread.join()
>>> total
[45]

```

## Trigger events from an async function

In an async program, `await` the trigger inside your coroutines. The next step starts when every
handler is done:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def fetch_all(manager: EventManager, urls: list[str]) -> None:
...     await manager.atrigger_event("fetch_start", {"count": len(urls)})
...     for url in urls:
...         await asyncio.sleep(0)  # a real program awaits a request here
...         await manager.atrigger_event("fetch_done", {"url": url})
...     await manager.atrigger_event("fetch_end")
>>> async def log_done(context: Context) -> None:
...     print(f"fetched {context['url']}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "fetch_start", lambda context: print(f"fetching {context['count']} urls")
... )
>>> _ = manager.add_event_handler("fetch_done", log_done)
>>> _ = manager.add_event_handler("fetch_end", lambda _: print("done"))
>>> asyncio.run(fetch_all(manager, ["a.com", "b.com"]))
fetching 2 urls
fetched a.com
fetched b.com
done

```

## Use options with coroutine handlers

`once`, `condition` and the `on` decorator work the same way with coroutine
handlers:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager, PeriodicCondition
>>> manager = EventManager()
>>> @manager.on("epoch_end", condition=PeriodicCondition(freq=2))
... async def upload(context: Context) -> None:
...     await asyncio.sleep(0)
...     print(f"uploaded epoch {context['epoch']}")
>>> async def main() -> None:
...     for epoch in range(3):
...         await manager.atrigger_event("epoch_end", {"epoch": epoch, "loss": 0.5})
>>> asyncio.run(main())
uploaded epoch 0
uploaded epoch 2

```

## Run the work of a handler concurrently

The handlers of an event run sequentially, so a slow handler delays the next ones. To run several
awaitables at the same time, use `asyncio.gather` inside one handler:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def upload(name: str) -> str:
...     await asyncio.sleep(0)
...     return name
>>> async def upload_all(context: Context) -> None:
...     done = await asyncio.gather(*(upload(name) for name in context["files"]))
...     print(f"uploaded {done}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("training_end", upload_all)
>>> asyncio.run(manager.atrigger_event("training_end", {"files": ["a.pt", "b.pt"]}))
uploaded ['a.pt', 'b.pt']

```

Hand a long computation to an executor (`await loop.run_in_executor(...)` or `asyncio.to_thread`)
from a coroutine handler.

## Test a handler

A handler is a plain callable, so test it without a manager. Test the wiring with a mock:

```python
from unittest.mock import create_autospec

from minevent import Context, EventManager


def log_epoch(context: Context) -> None:
    print(f"epoch {context['epoch']}")


def test_epoch_end_calls_the_handler():
    manager = EventManager()
    handler = create_autospec(log_epoch)  # a mock with the signature of log_epoch
    manager.add_event_handler("epoch_end", handler)
    manager.trigger_event("epoch_end", {"epoch": 1})
    handler.assert_called_once_with({"epoch": 1})
```

An async handler is tested with `asyncio.run` (or the async support of your test framework):

```python
import asyncio
from unittest.mock import create_autospec

from minevent import Context, EventManager


async def upload(context: Context) -> None:
    await asyncio.sleep(0)


def test_epoch_end_awaits_the_handler():
    manager = EventManager()
    handler = create_autospec(upload)  # an async mock with the signature of upload
    manager.add_event_handler("epoch_end", handler)
    asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 1}))
    handler.assert_awaited_once_with({"epoch": 1})
```
