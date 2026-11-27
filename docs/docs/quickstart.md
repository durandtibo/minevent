# Quickstart

`minevent` has three concepts:

- an **event** is a string that names something that happens;
- an **event handler** is a callable that runs when the event happens;
- an **event manager** stores the handlers and triggers the events.

This page shows one example of each feature. The [how it works page](architecture.md) states the
rules of the library, and the [examples](examples.md) combine the features. To install it, see
[Get Started](get_started.md).

## Register a handler and trigger an event

Create an `EventManager`, add a handler to an event and trigger the event. A handler is called with
the context of the trigger, and `_` shows that this one does not use it (see
[the calling rule](architecture.md#the-calling-rule)):

```pycon
>>> from minevent import Context, EventManager
>>> def hello_handler(_: Context) -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("training_end", hello_handler)
>>> manager.trigger_event("training_end")
Hello!

```

An event can have several handlers:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler("training_end", lambda _: print("save the model"))
>>> _ = manager.add_event_handler("training_end", lambda _: print("send a report"))
>>> manager.trigger_event("training_end")
save the model
send a report
>>> manager
EventManager(events={'training_end': 2})
>>> manager.events
['training_end']

```

The decorator `on` registers a function:

```pycon
>>> from minevent import Context, EventManager
>>> manager = EventManager()
>>> @manager.on("training_start")
... def log_start(_: Context) -> None:
...     print("start")
>>> manager.trigger_event("training_start")
start

```

## Pass data to the handlers

The second argument of `trigger_event` is the payload, a dict for example. The handlers read it in a
`Context`, with `context["key"]` for a required value and `context.get("key")` for an optional one:

```pycon
>>> from minevent import Context, EventManager
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}, loss {context.get('loss', 'unknown')}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> manager.trigger_event("epoch_end", {"epoch": 1, "loss": 0.5})
epoch 1, loss 0.5
>>> manager.trigger_event("epoch_end", {"epoch": 2})
epoch 2, loss unknown

```

The arguments that do not come from the payload can be bound with `functools.partial`:

```pycon
>>> import functools
>>> from minevent import Context, EventManager
>>> def save(path: str, context: Context) -> None:
...     print(f"save epoch {context['epoch']} to {path}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", functools.partial(save, "model.pt"))
>>> manager.trigger_event("epoch_end", {"epoch": 3})
save epoch 3 to model.pt

```

## Control when a handler runs

A **condition** is a function of the context that returns a boolean, such as `PeriodicCondition`:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda _: print("checkpoint"), condition=PeriodicCondition(freq=2)
... )
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda _: print("late epoch"),
...     condition=lambda context: context["epoch"] >= 2,
... )
>>> for epoch in range(3):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
checkpoint
checkpoint
late epoch

```

With `once=True`, a handler runs at most once:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", lambda _: print("first epoch"), once=True)
>>> manager.trigger_event("epoch_end")
first epoch
>>> manager.trigger_event("epoch_end")

```

## Remove a handler

`add_event_handler` returns a `Subscription`, which removes the registration:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("epoch_end", lambda _: print("epoch"))
>>> subscription.remove()
True
>>> subscription.remove()
False
>>> manager.trigger_event("epoch_end")

```

A `with` block scopes a registration, `clear_event` removes the handlers of an event, and `reset`
removes all the handlers:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> with manager.add_event_handler("batch_end", lambda _: print("batch")):
...     manager.trigger_event("batch_end")
batch
>>> _ = manager.add_event_handler("batch_end", lambda _: None)
>>> _ = manager.add_event_handler("epoch_end", lambda _: None)
>>> manager.clear_event("batch_end")
>>> manager.events
['epoch_end']
>>> manager.reset()
>>> manager
EventManager(events={})

```

## Look at the registrations

`events` lists the events that have a handler, `in` tests one event, and `get_subscriptions` returns
the registrations of an event, in the order they run:

```pycon
>>> from minevent import Context, EventManager
>>> def log_epoch(_: Context) -> None:
...     print("epoch")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch, once=True)
>>> manager.events
['epoch_end']
>>> "batch_end" in manager
False
>>> manager.get_subscriptions("epoch_end")
(Subscription(event='epoch_end', handler='log_epoch', once=True),)

```

## Coroutine handlers

Trigger an event with `atrigger_event` to await its coroutine handlers. It runs the synchronous
handlers too:

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def hello_handler(context: Context) -> None:
...     print(f"Hello {context['name']}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> _ = manager.add_event_handler("my_event", lambda _: print("done"))
>>> asyncio.run(manager.atrigger_event("my_event", {"name": "John"}))
Hello John!
done

```

## Errors

An exception of a handler reaches the caller of the trigger, with a note that says which handler
raised it:

```pycon
>>> from minevent import Context, EventManager
>>> def log_loss(context: Context) -> None:
...     print(context["loss"])
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_loss)
>>> try:
...     manager.trigger_event("epoch_end", {"epoch": 1})
... except KeyError as exc:
...     print(exc)
...     print(exc.__notes__[0])
"key 'loss' not found in the context; available keys: ['epoch']"
raised by log_loss while handling the event 'epoch_end'

```

## Next steps

- [Examples](examples.md): recipes for training loops, plugins, async programs and tests.
- [User guide](guide.md): recommendations and troubleshooting.
- [How it works](architecture.md): the rules, the guarantees and the limits.
- [Design choices](design.md): the reasons and the trade-offs.
- [Reference](refs/index.md): the signatures of the classes.
