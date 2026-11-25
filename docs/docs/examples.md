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
...         manager.trigger_event("epoch_end", {"epoch": epoch, "loss": loss})
...     manager.trigger_event("training_end")
>>> manager = EventManager()
>>> train(manager, epochs=2)
>>> _ = manager.add_event_handler("training_start", lambda: print("Training started"))
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda context: print(f"epoch {context['epoch']}: loss={context['loss']}")
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
...     lambda context: print(f"checkpoint at epoch {context['epoch']}"),
...     condition=PeriodicCondition(freq=3, skip_first=True),
... )
>>> for epoch in range(7):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
checkpoint at epoch 3
checkpoint at epoch 6

```

`AfterNCondition(n)` is `False` for the first `n` calls, which is useful for a warm-up:

```pycon
>>> from minevent import AfterNCondition, EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"validate at epoch {context['epoch']}"),
...     condition=AfterNCondition(2),
... )
>>> for epoch in range(4):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
validate at epoch 2
validate at epoch 3

```

## Write a custom condition

A condition is any function that returns a boolean, without parameter or with the `Context` of the
trigger (see the next example). A class with `__call__` is useful when the condition has a state or
reads another object:

```pycon
>>> from minevent import EventManager
>>> class Flag:
...     def __init__(self) -> None:
...         self.enabled = False
...
...     def __call__(self) -> bool:
...         return self.enabled
>>> verbose = Flag()
>>> manager = EventManager()
>>> _ = manager.add_event_handler("batch_end", lambda: print("batch done"), condition=verbose)
>>> manager.trigger_event("batch_end")
>>> verbose.enabled = True
>>> manager.trigger_event("batch_end")
batch done

```

To combine conditions, write a function, for example `condition=lambda: a() and b()`.

## Decide from the payload

A condition that has a parameter is called with the same read-only `Context` as the handlers, so it
can depend on the payload of the trigger. A condition without parameter is called without argument.
A handler and its condition can read different keys:

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

The built-in conditions (`PeriodicCondition`, `AfterNCondition`) take no parameter. To combine one
with a condition on the payload, write a function that calls it:
`condition=lambda context: periodic() and is_improving(context)`.

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

## Share an event between handlers with different needs

Each handler receives the same read-only `Context` and reads the keys that it needs. A handler
decides what to do with a missing key: `context["lr"]` raises a `KeyError`, and
`context.get("lr", 0.1)` returns a default:

```pycon
>>> from minevent import Context, EventManager
>>> def log_loss(context: Context) -> None:
...     print(f"loss {context['loss']}")
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}, lr {context.get('lr', 0.1)}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_loss)
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> manager.trigger_event("epoch_end", {"epoch": 3, "loss": 0.5})
loss 0.5
epoch 3, lr 0.1

```

## Register with a decorator

`on` registers a function and returns it unchanged, so the function can still be called directly. It
takes the same options as `add_event_handler`:

```pycon
>>> from minevent import Context, EventManager, PeriodicCondition
>>> manager = EventManager()
>>> @manager.on("epoch_end", condition=PeriodicCondition(freq=2))
... def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}")
>>> for epoch in range(3):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
epoch 0
epoch 2
>>> log_epoch(Context({"epoch": 10}))
epoch 10

```

## Pass a dict or a Context

`trigger_event` takes the data of the trigger as a dict, or as a `Context`. Both give the handlers
the same read-only `Context`. A dict is copied and validated at each trigger, while a `Context` is
validated once, when it is built, and is passed as is, so build it once to reuse it:

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

## Bind fixed arguments

Use `functools.partial` for the arguments that do not come from the payload. The context is passed
after the bound arguments:

```pycon
>>> import functools
>>> from minevent import Context, EventManager
>>> def save(path: str, context: Context) -> None:
...     print(f"save epoch {context['epoch']} to {path}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", functools.partial(save, "model.pt"))
>>> manager.trigger_event("epoch_end", {"epoch": 4})
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
>>> len(manager)
0

```

## Use coroutine handlers

`atrigger_event` awaits the coroutine handlers and also runs the synchronous ones, one after the
other, in the registration order. `trigger_event` raises a `TypeError` for a coroutine handler:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def notify(context: Context) -> None:
...     await asyncio.sleep(0)
...     print(f"notified epoch {context['epoch']}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", lambda context: print(f"epoch {context['epoch']}"))
>>> _ = manager.add_event_handler("epoch_end", notify)
>>> asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 1}))
epoch 1
notified epoch 1

```

## Trigger events from an async function

In an async program, `await` the trigger inside your coroutines. The handlers of an event still run
one after the other, so the next step starts when every handler is done:

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
>>> _ = manager.add_event_handler("fetch_end", lambda: print("done"))
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

A synchronous handler blocks the event loop while it runs: hand a long computation to an executor
(`await loop.run_in_executor(...)` or `asyncio.to_thread`) from a coroutine handler.

## Handle an async handler used with trigger_event

`trigger_event` is synchronous, so it cannot await a coroutine. It closes the coroutine and raises a
`TypeError` that names the handler, instead of silently dropping it:

```pycon
>>> from minevent import EventManager
>>> async def notify() -> None:
...     print("notified")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", notify)
>>> try:
...     manager.trigger_event("my_event")
... except TypeError as exc:
...     print(exc)
notify returned an awaitable; use atrigger_event

```

## Handle the errors of a handler

A handler that raises stops the dispatch, and the exception reaches the caller with a note that
names the event and the handler:

```pycon
>>> from minevent import EventManager
>>> def fail() -> None:
...     raise ValueError("boom")
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
    manager.trigger_event("epoch_end", {"epoch": 1})
    handler.assert_called_once_with({"epoch": 1})
```

An async handler is tested with `asyncio.run` (or the async support of your test framework):

```python
import asyncio
from unittest.mock import AsyncMock

from minevent import EventManager


def test_epoch_end_awaits_the_handler():
    manager = EventManager()
    handler = AsyncMock()
    manager.add_event_handler("epoch_end", handler)
    asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 1}))
    handler.assert_awaited_once_with({"epoch": 1})
```
