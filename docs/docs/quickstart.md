# quickstart

## Overview

The `minevent` event system is composed of three main components:

- an event
- an event handler
- an event manager

It is a synchronous system i.e. only one event and event handler are executed at the same time.
This page presents the design used in `minevent`, but other designs exist.
The proposed design was not designed to work in all the scenarios, so it is highly recommended to
read the documentation to understand if it fits your needs/requirements before to use it.

## Event

In `minevent`, an event is a string that represents something happening.
The event is represented by the event name.
For example, it is possible to write the following line to define an event that happens after the
training is completed.

```pycon
my_event = "training completed"
```

## Event handler

In `minevent`, an event handler is a piece a code that is executed when an even happened.

An event handler must have a `handle` method, which executes a piece of code when the event
happens. Event handlers are compared by identity.

`minevent` provides `EventHandler`, which wraps a callable. It can take an optional `condition`
to execute the logic only when the condition is true.

### Basic event handler

Let's assume we want to create an event handler to say hello when an event is fired.
It is possible to implement this scenario as follow by using `minvent.EventHandler`.

```pycon
>>> from minevent import EventHandler
>>> def hello_handler() -> None:
...     print("Hello!")
>>> handler = EventHandler(hello_handler)
>>> handler.handle()
Hello!

```

### Event handler with arguments

The previous example has no arguments.
It is also possible to provide some arguments to customize the event handler.
The arguments can be given as positional arguments using `handler_args`:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> handler = EventHandler(hello_handler, handler_args=("Bob", "Monday"))
>>> handler.handle()
Hello Bob! Happy Monday!

```

It is also possible to give the arguments as keyword arguments using `handler_kwargs`:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> handler = EventHandler(hello_handler, handler_kwargs={"name": "Bob", "day": "Monday"})
>>> handler.handle()
Hello Bob! Happy Monday!

```

It is also possible to use `handler_args` and `handler_kwargs`:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
>>> handler = EventHandler(hello_handler, handler_args=["Bob"], handler_kwargs={"day": "Monday"})
>>> handler.handle()
Hello Bob! Happy Monday!

```

It is possible to define event handlers with a large range of functions.
For example, it is possible to implement the same logic by using directly `print`:

```pycon
>>> from minevent import EventHandler
>>> handler = EventHandler(print, handler_args=("Hello Bob! Happy Monday!",))
>>> handler.handle()
Hello Bob! Happy Monday!

```

### Event handler with condition

It is possible to define an event handler that is executed when a condition is true.
The following example shows how to define an event handler where the logic is executed every three
calls.

```pycon
>>> from minevent import EventHandler, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
>>> handler = EventHandler(hello_handler, condition=PeriodicCondition(freq=3))
>>> handler.handle()
Hello!
>>> handler.handle()
>>> handler.handle()
>>> handler.handle()
Hello!

```

`PeriodicCondition` is a condition implemented in `minevent` to execute an event handler with a
periodic pattern.
It is also possible to implement custom conditions.
If the condition returns `True`, the logic associated to the event handler is executed, otherwise
the logic associated to the event handler is not executed.

A plain function without argument that returns a boolean is also accepted as a condition:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler() -> None:
...     print("Hello!")
>>> verbose = True
>>> handler = EventHandler(hello_handler, condition=lambda: verbose)
>>> handler.handle()
Hello!

```

A condition is any function without argument that returns a boolean (the `Condition` protocol).
`minevent` provides the stateful conditions `OnceCondition` (first call only),
`AfterNCondition` (skip the first `n` calls) and `PeriodicCondition(freq, skip_first=...)`. A class
with a `__call__` method is a condition too.

To combine conditions, write a function. You choose which conditions are evaluated:

```pycon
>>> from minevent import AfterNCondition, EventHandler, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
>>> after_one, periodic = AfterNCondition(1), PeriodicCondition(2)
>>> handler = EventHandler(hello_handler, condition=lambda: all([after_one(), periodic()]))
>>> for _ in range(5):
...     handler.handle()
Hello!
Hello!

```

`all([a(), b()])` evaluates every condition at each call, so stateful conditions advance together.
`a() and b()` skips `b` when `a` is `False`: use it when `b` is costly and stateless, because a
stateful `b` would not count the calls skipped by `a`.

Stateful conditions (`PeriodicCondition`, `OnceCondition`, `AfterNCondition`) keep their counter in
the instance. A condition instance given to two handlers is shared, so the two handlers advance the
same counter. Create one instance per handler (a small factory function is enough):

```pycon
>>> from minevent import EventHandler, PeriodicCondition
>>> def make_handler(name):
...     return EventHandler(print, handler_args=(name,), condition=PeriodicCondition(freq=2))
>>> first, second = make_handler("first"), make_handler("second")
>>> first.handle()
first
>>> second.handle()
second

```

`add_event_handler(..., once=True)` and `OnceCondition` are two ways to run a handler once. Prefer
`once=True` to run a handler on the next trigger of an event (the registration is removed). Use
`OnceCondition` when the handler stays registered, for example inside a function that combines several conditions.

### Event handler identity

Event handlers are compared by identity: two `EventHandler`s created with the same arguments are
different objects. To find or remove a registration, keep the `Subscription` returned by
`EventManager.add_event_handler` (see [Subscriptions](#subscriptions)).

```pycon
>>> from minevent import EventHandler
>>> handler = EventHandler(print)
>>> handler == handler
True
>>> handler == EventHandler(print)
False

```

## Event manager

- [Overview of the event manager](#overview-of-the-event-manager)
- [Create an event manager](#create-an-event-manager)
- [Add an event handler](#add-an-event-handler)
- [Subscriptions](#subscriptions)
- [Fire an event](#fire-an-event)
- [Remove an event handler](#remove-an-event-handler)
- [Reset the event manager](#reset-the-event-manager)
- [Internals](#internals)

### Overview of the event manager

As explained by its name, the goal of the event manager is to manage event handlers.
The event manager supports the following functionalities:

- adding an event handler
- firing all the event handlers associated to an event.
- removing an event handler from an event

### Create an event manager

To use the event system, it is important to create an event manager.
`minevent` implements an event manager, but it is possible to implement and use other compatible
event managers.
This documentation uses the default event manager implemented in `minevent`.
To create an event manager, you can write:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> manager
EventManager(events={})

```

The representation of the event manager shows the number of event handlers of each event.
The event manager is empty, so it shows there is no event handler.

### Add an event handler

This section describes how to add an event handler to an event manager.
The method to add an event handler to the event manager is `add_event_handler`.
There are several approaches to add an event handler.

The simplest approach requires an event and an event handler.
The following example shows how to add a `hello_handler` handler to the `'my_event'` event.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(events={'my_event': 1})

```

You can see there is a registered event handler for the event name `my_event`.

It is possible to add an event handler that takes some input arguments.
The following example shows how to add an event handler with some positional arguments.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {last_name}, {first_name} {last_name}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler, ("John", "Smith")))
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler, ("Jane", "Doe")))
>>> manager
EventManager(events={'my_event': 2})

```

For a given event, the event handlers are ordered by using the order of addition.
The event handler `(0)` was added before the event handler `(1)`.
Internally, each event uses a list to store the registered event handlers.
It is possible to add the same event handler multiple times:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(events={'my_event': 2})

```

### Subscriptions

`add_event_handler` returns a `Subscription`, the registration of the handler. Its `remove()` method
removes exactly that registration, even if the same handler is registered several times, and
returns `False` if it was already removed:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> handler = EventHandler(hello_handler)
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
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> handler = EventHandler(hello_handler)
>>> for _ in range(5):
...     if not any(s.event_handler is handler for s in manager.get_subscriptions("my_event")):
...         _ = manager.add_event_handler("my_event", handler)
>>> len(manager)
1

```

To run a handler only on the next trigger, use `once=True`:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler), once=True)
>>> manager.trigger_event("my_event")
Hello!
>>> manager.trigger_event("my_event")

```

`once=True` means "the next trigger", not "the next time the handler runs": the registration is
removed on the next trigger even if the condition of the `EventHandler` is `False` and the
function is not called. If you need the handler to run the first time its condition is `True`,
register it without `once` and use `OnceCondition` as the condition.

A `Subscription` is a context manager that removes the registration when the block exits, and its
`active` property tells if the handler is still registered. `EventManager.on` is a decorator that
registers a function and returns it unchanged:

```pycon
>>> from minevent import EventHandler, EventManager
>>> manager = EventManager()
>>> with manager.add_event_handler("my_event", EventHandler(print, handler_args=("Hello!",))) as sub:
...     manager.trigger_event("my_event")
Hello!
>>> sub.active
False
>>> @manager.on("epoch_end")
... def log_epoch(epoch):
...     print(f"epoch {epoch}")
>>> manager.trigger_event("epoch_end", epoch=1)
epoch 1

```

### Fire an event

This section describes how to fire an event.
As explained above, it is possible to add a handler to an event.
Then, we want to execute the handler when the event is fired.
The following example shows how to fire the `hello_handler` for the event `'my_event'`:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(events={'my_event': 1})
>>> manager.trigger_event("my_event")
Hello!
>>> manager
EventManager(events={'my_event': 1})

```

You can note that the last fired event name has been updated.
The current last fired event name is `'my_event'`.
The event manager uses the arguments that were given when the event handler was added.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {first_name} {last_name}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler, ("John", "Smith")))
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler, ("Jane", "Doe")))
>>> manager
EventManager(events={'my_event': 2})
>>> manager.trigger_event("my_event")
Hello. I am John Smith
Hello. I am Jane Doe

```

As explained above, it is possible to add a condition to control when to execute the handler.
The following shows how to execute the `hello_handler` every 3 `'my_event'` events.

```pycon
>>> from minevent import EventHandler, PeriodicCondition, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "my_event", EventHandler(hello_handler, condition=PeriodicCondition(freq=3))
... )
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

Every handler receives the whole payload, so a handler that does not accept a key raises a
`TypeError`. Either accept the extra keys with `**_`, or create the handler with
`filter_payload=True` to pass only the keys its signature accepts:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def log_loss(loss):
...     print(f"loss {loss}")
>>> def log_epoch(epoch):
...     print(f"epoch {epoch}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", EventHandler(log_loss, filter_payload=True))
>>> _ = manager.add_event_handler("epoch_end", EventHandler(log_epoch, filter_payload=True))
>>> manager.trigger_event("epoch_end", epoch=3, loss=0.5)
loss 0.5
epoch 3

```

### Fire an event with coroutine handlers

`trigger_event` calls the handlers synchronously and raises a `TypeError` for a coroutine function
(the coroutine would never be awaited).
To use coroutine handlers, fire the event with `atrigger_event`, which awaits the coroutines (and
also runs synchronous handlers) one after the other, in the order they were added:

```pycon
>>> import asyncio
>>> from minevent import EventHandler, EventManager
>>> async def hello_handler(name: str) -> None:
...     print(f"Hello {name}!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> asyncio.run(manager.atrigger_event("my_event", name="John"))
Hello John!

```

### Remove an event handler

A previous section describes how to add an event handler, but sometimes it is useful to remove an
event handler. Call `remove()` on the `Subscription` returned by `add_event_handler`:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("my_event", EventHandler(hello_handler))
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
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> _ = manager.add_event_handler("my_event", EventHandler(print))
>>> _ = manager.add_event_handler("my_other_event", EventHandler(hello_handler))
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
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> _ = manager.add_event_handler("my_other_event", EventHandler(hello_handler))
>>> manager
EventManager(events={'my_event': 1, 'my_other_event': 1})
>>> manager.reset()
>>> manager
EventManager(events={})

```
