# Quickstart

## Overview

The `minevent` event system is composed of three main components:

- an event
- an event handler (a callable)
- an event manager

`trigger_event` is synchronous: the handlers of an event run one after the other, in the order they
were registered, in the calling thread. Coroutine handlers are supported by `atrigger_event` (see
[Fire an event with coroutine handlers](#fire-an-event-with-coroutine-handlers)).
This page presents the design used in `minevent`, but other designs exist.
The proposed design was not designed to work in all the scenarios, so it is highly recommended to
read the documentation to understand if it fits your needs and requirements before using it.

## Event

In `minevent`, an event is a string that represents something happening.
The event is represented by the event name.
For example, it is possible to write the following line to define an event that happens after the
training is completed.

```python
my_event = "training completed"
```

## Event handler

In `minevent`, an event handler is a piece of code that is executed when an event happens.

An event handler is a callable that needs no argument or only the context. It is called as
`handler(context)` if it has a parameter without default, and as `handler()` otherwise, where
`context` is a read-only `Context` that holds the data given when the event is triggered (see
[Fire an event](#fire-an-event)). A parameter that has a default keeps it, and any other signature
is rejected at registration (see the
[calling rule](architecture.md#the-calling-rule)). A coroutine function is a handler of
`atrigger_event`. The options of a registration (`once` and `condition`) are the keyword-only
arguments of `EventManager.add_event_handler`.

### Basic event handler

Let's assume we want to create an event handler to say hello when an event is fired.
A function is a handler:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> manager.trigger_event("my_event")
Hello!

```

### Event handler with arguments

The previous example has no arguments.
It is also possible to provide some arguments to customize the event handler.
Use `functools.partial` to bind the arguments that do not come from the payload. The arguments can
be given as positional arguments:

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "Bob", "Monday"))
>>> manager.trigger_event("my_event")
Hello Bob! Happy Monday!

```

as keyword arguments:

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "my_event", functools.partial(hello_handler, name="Bob", day="Monday")
... )
>>> manager.trigger_event("my_event")
Hello Bob! Happy Monday!

```

or both:

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "Bob", day="Monday"))
>>> manager.trigger_event("my_event")
Hello Bob! Happy Monday!

```

It is possible to define event handlers with a large range of functions.
For example, it is possible to implement the same logic with a lambda function. A callable that
accepts `*args`, like `print`, does not say whether it expects the context, so it is rejected: wrap
it in a function or a lambda that says what it needs:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", lambda: print("Hello Bob! Happy Monday!"))
>>> manager.trigger_event("my_event")
Hello Bob! Happy Monday!

```

### Event handler with condition

It is possible to define an event handler that is executed when a condition is true.
The following example shows how to define an event handler where the logic is executed every three
calls.

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler, condition=PeriodicCondition(freq=3))
>>> manager.trigger_event("my_event")
Hello!
>>> manager.trigger_event("my_event")
>>> manager.trigger_event("my_event")
>>> manager.trigger_event("my_event")
Hello!

```

`PeriodicCondition` is a condition implemented in `minevent` to execute an event handler with a
periodic pattern.
It is also possible to implement custom conditions.
If the condition returns `True`, the logic associated to the event handler is executed, otherwise
the logic associated to the event handler is not executed.

A plain function without argument that returns a boolean is also accepted as a condition:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> verbose = True
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler, condition=lambda: verbose)
>>> manager.trigger_event("my_event")
Hello!

```

A condition is any function that returns a boolean (a `Condition`). Like a handler, it is called as
`condition(context)` with the read-only `Context` of the trigger if it has a parameter without
default, and as `condition()` otherwise, so it can depend on the payload:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda: print("late epoch"),
...     condition=lambda context: context.get("epoch", 0) >= 2,
... )
>>> manager.trigger_event("epoch_end", {"epoch": 1})
>>> manager.trigger_event("epoch_end", {"epoch": 2})
late epoch

```

`minevent` provides the stateful conditions `AfterNCondition` (skip the
first `n` calls) and `PeriodicCondition(freq, skip_first=...)`. A class with a `__call__` method
is a condition too.

To combine conditions, write a function. You choose which conditions are evaluated:

```pycon
>>> from minevent import AfterNCondition, EventManager, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
>>> after_one, periodic = AfterNCondition(1), PeriodicCondition(2)
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "my_event", hello_handler, condition=lambda: all([after_one(), periodic()])
... )
>>> for _ in range(5):
...     manager.trigger_event("my_event")
Hello!
Hello!

```

`all([a(), b()])` evaluates every condition at each call, so stateful conditions advance together.
`a() and b()` skips `b` when `a` is `False`: use it when `b` is costly and stateless, because a
stateful `b` would not count the calls skipped by `a`.

Stateful conditions (`PeriodicCondition`, `AfterNCondition`) keep their counter in
the instance. A condition instance given to two handlers is shared, so the two handlers advance the
same counter. Create one instance per handler (a small factory function is enough):

```pycon
>>> import functools
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> def say(name):
...     print(name)
>>> def register(name):
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

To run a handler once, use `add_event_handler(..., once=True)`: the registration is removed just
before its handler runs, on the next trigger of the event whose condition is `True`.

### Event handler identity

Registrations are identified by the `Subscription` that `EventManager.add_event_handler` returns,
not by the handler: the same callable can be registered several times. To find or remove a
registration, keep the `Subscription` (see [Subscriptions](#subscriptions)).

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> first = manager.add_event_handler("my_event", hello_handler)
>>> second = manager.add_event_handler("my_event", hello_handler)
>>> first == second
False
>>> first.handler is second.handler
True

```

## Event manager

- [Overview of the event manager](#overview-of-the-event-manager)
- [Create an event manager](#create-an-event-manager)
- [Add an event handler](#add-an-event-handler)
- [Subscriptions](#subscriptions)
- [Fire an event](#fire-an-event)
- [Remove an event handler](#remove-an-event-handler)
- [Reset the event manager](#reset-the-event-manager)

### Overview of the event manager

As explained by its name, the goal of the event manager is to manage event handlers.
The event manager supports the following functionalities:

- adding an event handler, which returns a `Subscription` (`add_event_handler`, `on`)
- firing all the event handlers associated to an event, with an optional payload
  (`trigger_event`, `atrigger_event`)
- inspecting the registrations (`events`, `get_subscriptions`, `len(manager)`)
- removing an event handler from an event (`Subscription.remove`, `clear_event`, `reset`)

### Create an event manager

To use the event system, it is important to create an event manager.
`minevent` implements one event manager, `EventManager`. It has no global state, so you create an
instance and pass it where it is needed.
To create an event manager, you can write:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> manager
EventManager(events={})

```

The representation of the event manager shows the number of event handlers of each event.
The event manager is empty, so it shows there is no event handler. `manager.events` lists the
events that have at least one handler, and `"my_event" in manager` tests one.

### Add an event handler

This section describes how to add an event handler to an event manager.
The method to add an event handler to the event manager is `add_event_handler`.
There are several approaches to add an event handler.

The simplest approach requires an event and an event handler.
The following example shows how to add a `hello_handler` handler to the `'my_event'` event.

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> manager
EventManager(events={'my_event': 1})

```

You can see there is a registered event handler for the event name `my_event`.

It is possible to add an event handler that takes some input arguments.
The following example shows how to add an event handler with some positional arguments.

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {last_name}, {first_name} {last_name}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "John", "Smith"))
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "Jane", "Doe"))
>>> manager
EventManager(events={'my_event': 2})

```

For a given event, the event handlers run in the order of addition: here, the handler of
John Smith runs before the handler of Jane Doe.
Internally, each event stores its registrations in an ordered `dict`.
It is possible to add the same event handler multiple times:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> manager
EventManager(events={'my_event': 2})

```

### Subscriptions

`add_event_handler` returns a `Subscription`, the registration of the handler. Its `remove()` method
removes exactly that registration, even if the same handler is registered several times, and
returns `False` if it was already removed:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> handler = hello_handler
>>> first = manager.add_event_handler("my_event", handler)
>>> second = manager.add_event_handler("my_event", handler)
>>> first.remove()
True
>>> first.remove()
False
>>> second.active
True
>>> manager.trigger_event("my_event")
Hello!

```

`get_subscriptions` returns the registrations of an event, in the order the handlers run, and
`len(manager)` is the total number of registrations. If you want to add an event handler only once,
check the registrations:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> handler = hello_handler
>>> for _ in range(5):
...     if not any(s.handler is handler for s in manager.get_subscriptions("my_event")):
...         _ = manager.add_event_handler("my_event", handler)
>>> len(manager)
1

```

To run a handler only once, use `once=True`:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler, once=True)
>>> manager.trigger_event("my_event")
Hello!
>>> manager.trigger_event("my_event")

```

`once=True` means "the first time the handler runs": a condition that is `False` does not consume
the registration, which waits for the first trigger where the condition is `True`:

```pycon
>>> from minevent import AfterNCondition, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler, once=True, condition=AfterNCondition(2))
>>> manager.trigger_event("my_event")
>>> manager.trigger_event("my_event")
>>> manager.trigger_event("my_event")
Hello!
>>> manager.trigger_event("my_event")

```

A `Subscription` is a context manager that removes the registration when the block exits, and its
`active` property tells if the handler is still registered. `EventManager.on` is a decorator that
registers a function and returns it unchanged. It takes the options `once` and `condition`:

```pycon
>>> from minevent import Context, EventManager
>>> manager = EventManager()
>>> with manager.add_event_handler("my_event", lambda: print("Hello!")) as sub:
...     manager.trigger_event("my_event")
Hello!
>>> sub.active
False
>>> @manager.on("epoch_end")
... def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}")
>>> manager.trigger_event("epoch_end", {"epoch": 1})
epoch 1

```

### Fire an event

This section describes how to fire an event.
As explained above, it is possible to add a handler to an event.
Then, we want to execute the handler when the event is fired.
The following example shows how to fire the `hello_handler` for the event `'my_event'`:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> manager
EventManager(events={'my_event': 1})
>>> manager.trigger_event("my_event")
Hello!
>>> manager
EventManager(events={'my_event': 1})

```

Triggering an event does not change the manager: the representation above is the same before and
after. A handler is called as `handler(context)`, where `context` holds the data given to
`trigger_event` (see below), or as `handler()` if it has no parameter without default. The arguments
that do not come from the payload are bound with `functools.partial`.

```pycon
>>> import functools
>>> from minevent import EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {first_name} {last_name}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "John", "Smith"))
>>> _ = manager.add_event_handler("my_event", functools.partial(hello_handler, "Jane", "Doe"))
>>> manager
EventManager(events={'my_event': 2})
>>> manager.trigger_event("my_event")
Hello. I am John Smith
Hello. I am Jane Doe

```

As explained above, it is possible to add a condition to control when to execute the handler.
The following shows how to execute the `hello_handler` every 3 `'my_event'` events.

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler, condition=PeriodicCondition(freq=3))
>>> manager
EventManager(events={'my_event': 1})
>>> for i in range(10):
...     print(f"i={i}")
...     manager.trigger_event("my_event")
i=0
Hello!
i=1
i=2
i=3
Hello!
i=4
i=5
i=6
Hello!
i=7
i=8
i=9
Hello!

```

The `trigger_event` method does nothing if there is no event handler registered for the event:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> manager.trigger_event("my_event")

```

### Share an event between handlers that need different payload keys

The dict given to `trigger_event` is copied into one read-only `Context` that is shared by the
handlers. You can also give a `Context` yourself, `trigger_event("epoch_end", Context({...}))`: it
is passed as is, so it can be reused for several triggers. Each handler reads the keys it needs:
`context["key"]` raises a `KeyError` (that lists the available keys) if the key is missing, and
`context.get("key", default)` returns a default. An extra key never breaks a handler:

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

### Fire an event with coroutine handlers

`trigger_event` calls the handlers synchronously and raises a `TypeError` for a coroutine function
(the coroutine would never be awaited).
To use coroutine handlers, fire the event with `atrigger_event`, which awaits the coroutines (and
also runs synchronous handlers) one after the other, in the order they were added:

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

### Remove an event handler

A previous section describes how to add an event handler, but sometimes it is useful to remove an
event handler. Call `remove()` on the `Subscription` returned by `add_event_handler`:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("my_event", hello_handler)
>>> manager
EventManager(events={'my_event': 1})
>>> subscription.remove()
True
>>> manager
EventManager(events={})

```

If you did not keep the subscription, `get_subscriptions` returns the registrations of an event, and
`clear_event` removes all the event handlers of an event:

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> _ = manager.add_event_handler("my_event", lambda: None)
>>> _ = manager.add_event_handler("my_other_event", hello_handler)
>>> manager.get_subscriptions("my_event")[0].remove()
True
>>> manager
EventManager(events={'my_event': 1, 'my_other_event': 1})
>>> manager.clear_event("my_event")
>>> manager
EventManager(events={'my_other_event': 1})

```

### Reset the event manager

It is possible to reset the event manager with the `reset` method. It removes all the event handlers
and makes their subscriptions inactive. It is equivalent to create a new event manager.

```pycon
>>> from minevent import EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", hello_handler)
>>> _ = manager.add_event_handler("my_other_event", hello_handler)
>>> manager
EventManager(events={'my_event': 1, 'my_other_event': 1})
>>> manager.reset()
>>> manager
EventManager(events={})

```
