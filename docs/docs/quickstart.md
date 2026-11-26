# Quickstart

`minevent` has three concepts:

- an **event** is a case-sensitive string that names something that happens;
- an **event handler** is a callable that runs when the event happens;
- an **event manager** stores the handlers and triggers the events.

This page shows how to register a handler, trigger an event, pass data and remove a handler. The
[examples](examples.md) show more recipes, and the [how it works page](architecture.md) states the
rules of the library. To install it, see [Get Started](get_started.md).

## Register a handler and trigger an event

Create an `EventManager`, add a handler to an event and trigger the event:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("training_end", hello_handler)
>>> manager.trigger_event("training_end")
Hello!

```

The manager has no global state: create one instance and pass it where it is needed. Triggering an
event that has no handler does nothing. The handlers of an event run one after the other, in the
order they were added:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler("training_end", lambda: print("save the model"))
>>> _ = manager.add_event_handler("training_end", lambda: print("send a report"))
>>> manager.trigger_event("training_end")
save the model
send a report
>>> manager
EventManager(events={'training_end': 2})
>>> manager.events
['training_end']

```

The decorator `on` registers a function and returns it unchanged:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> @manager.on("training_start")
... def log_start() -> None:
...     print("start")
>>> manager.trigger_event("training_start")
start

```

## Pass data to the handlers

The second argument of `trigger_event` is the payload, a dict for example. A handler that has a
parameter receives it in a read-only `Context`; a handler without parameter ignores it:

```pycon
>>> from minevent import Context, EventManager
>>> def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}, loss {context.get('loss', 'unknown')}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", log_epoch)
>>> _ = manager.add_event_handler("epoch_end", lambda: print("done"))
>>> manager.trigger_event("epoch_end", {"epoch": 1, "loss": 0.5})
epoch 1, loss 0.5
done
>>> manager.trigger_event("epoch_end", {"epoch": 2})
epoch 2, loss unknown
done

```

`context["epoch"]` reads a required value and raises a `KeyError` if it is missing, and
`context.get("loss")` reads an optional one. The arguments that do not come from the payload are
bound with `functools.partial`:

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

A handler needs no argument or only the context. A callable such as `print` is rejected when it is
registered: wrap it in a function or a lambda (see
[the calling rule](architecture.md#the-calling-rule)).

## Control when a handler runs

A **condition** is a function that returns a boolean: the handler runs only if it returns `True`.
`PeriodicCondition` is provided, and a condition can read the payload:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda: print("checkpoint"), condition=PeriodicCondition(freq=2)
... )
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda: print("late epoch"),
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
>>> _ = manager.add_event_handler("epoch_end", lambda: print("first epoch"), once=True)
>>> manager.trigger_event("epoch_end")
first epoch
>>> manager.trigger_event("epoch_end")

```

## Remove a handler

`add_event_handler` returns a `Subscription`, the registration of the handler. Its `remove()` method
removes that registration only:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("epoch_end", lambda: print("epoch"))
>>> subscription.remove()
True
>>> subscription.remove()
False
>>> manager.trigger_event("epoch_end")

```

A `with` block removes the registration when it exits. `clear_event` removes all the handlers of an
event, and `reset` removes all the handlers:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> with manager.add_event_handler("batch_end", lambda: print("batch")):
...     manager.trigger_event("batch_end")
batch
>>> _ = manager.add_event_handler("batch_end", lambda: None)
>>> _ = manager.add_event_handler("epoch_end", lambda: None)
>>> manager.clear_event("batch_end")
>>> manager.events
['epoch_end']
>>> manager.reset()
>>> manager
EventManager(events={})

```

## Coroutine handlers

Trigger an event with `atrigger_event` to await its coroutine handlers (`trigger_event` raises a
`TypeError` for them):

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def hello_handler(context: Context) -> None:
...     print(f"Hello {context['name']}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> asyncio.run(manager.atrigger_event("my_event", {"name": "John"}))
Hello John!

```

## Errors

An exception of a handler reaches the caller of the trigger, and the next handlers are skipped. A
note says which handler raised it:

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
- [User guide](guide.md): recommendations, pitfalls and troubleshooting.
- [How it works](architecture.md): the rules, the guarantees and the limits.
- [Design choices](design.md): the reasons and the trade-offs.
- [Reference](refs/index.md): the signatures of the classes.
