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

An event handler must have two methods:

- `handle` which executes a piece of code when the event happens.
- `equal` which is used to compare two event handlers.

`minevent` provides two event handlers:

- `EventHandler` which is a simple event handler
- `ConditionalEventHandler` which is an extension of `EventHandler` to execute the logic only when a
  condition is true.

### Basic event handler

Let's assume we want to create an event handler to say hello when an event is fired.
It is possible to implement this scenario as follow by using `minvent.EventHandler`.

```pycon
>>> from minevent import EventHandler
>>> def hello_handler() -> None:
...     print("Hello!")
...
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
...
>>> handler = EventHandler(hello_handler, handler_args=("Bob", "Monday"))
>>> handler.handle()
Hello Bob! Happy Monday!

```

It is also possible to give the arguments as keyword arguments using `handler_kwargs`:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
...
>>> handler = EventHandler(hello_handler, handler_kwargs={'name': "Bob", 'day': "Monday"})
>>> handler.handle()
Hello Bob! Happy Monday!

```

It is also possible to use `handler_args` and `handler_kwargs`:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler(name: str, day: str) -> None:
...     print(f"Hello {name}! Happy {day}!")
...
>>> handler = EventHandler(hello_handler, handler_args=["Bob"], handler_kwargs={'day': "Monday"})
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
>>> from minevent import ConditionalEventHandler, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> handler = ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3))
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
If the condition returns ``True``, the logic associated to the event handler is executed, otherwise
the logic associated to the event handler is not executed.

### Event handler comparison

It is possible to compare event handlers by using the `equal` method.
Two `EventHandler`s are equal if they have the same handler and the same arguments:

```pycon
>>> from minevent import EventHandler
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> handler = EventHandler(hello_handler)
>>> handler.equal(EventHandler(hello_handler))
True
>>> handler.equal(EventHandler(print, handler_args=("Hello Bob! Happy Monday!",)))
False

```

Two `EventHandler`s are equal if they have the same handler, the same arguments and the same
condition:

```pycon
>>> from minevent import ConditionalEventHandler, PeriodicCondition
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> handler = ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3))
>>> handler.equal(ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3)))
True
>>> handler.equal(ConditionalEventHandler(hello_handler, PeriodicCondition(freq=2)))
False

```

## Event manager

- [Overview of the event manager](#overview-of-the-event-manager)
- [Create an event manager](#create-an-event-manager)
- [Add an event handler](#add-an-event-handler)
- [Check the presence of an event handler](#check-the-presence-of-an-event-handler)
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
EventManager(
  (event_handlers):
  (last_triggered_event): None
)

```

The main pieces of information about the experiment manager state are the list of event handlers for
each event name, and the last fired event name.
The event manager is empty, so it shows there is no event handler.
In this example, there was no event fired so the last fired event name is `None`.

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
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
        (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)

```

You can see there is a registered event handler for the event name `my_event`.

It is possible to add an event handler that takes some input arguments.
The following example shows how to add an event handler with some positional arguments.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {last_name}, {first_name} {last_name}")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler, ('John', 'Smith')))
>>> manager.add_event_handler("my_event", EventHandler(hello_handler, ('Jane', 'Doe')))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ('John', 'Smith')
          (handler_kwargs): {}
        )
      (1): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ('Jane', 'Doe')
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)

```

For a given event, the event handlers are ordered by using the order of addition.
The event handler `(0)` was added before the event handler `(1)`.
Internally, each event uses a list to store the registered event handlers.
It is possible to add the same event handler multiple times:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
      (1): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)

```

### Check the presence of an event handler

It is possible to check if an event handler is in the event manager by using the `has_event_handler`
method.
Sometimes, it may be important to check if an event handler is not already added before to add it.
The following code shows how to check if the `hello_handler` handler is registered at least one time
in the event manager:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.has_event_handler(EventHandler(hello_handler))
False
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.has_event_handler(EventHandler(hello_handler))
True

```

Note that it is not necessary to specify an event.
If no event is specified, this method checks if the handler is present in any of the events.
It is possible to specify an event to check if a handler is registered for a given event.
The following code shows how to check if the `hello_handler` handler is registered for
the `'my_event'` event:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
False
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.has_event_handler(EventHandler(hello_handler), "my_event")
True
>>> manager.has_event_handler(EventHandler(hello_handler), "my_other_event")
False

```

If you want to add an event handler only once, you can write something like:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> for _ in range(5):
...     if not manager.has_event_handler(EventHandler(hello_handler), "my_event"):
...         manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)

```

The `hello_handler` handler has been added only one time to the `'my_event'` event.

### Fire an event

This section describes how to fire an event.
As explained above, it is possible to add a handler to an event.
Then, we want to execute the handler when the event is fired.
The following example shows how to fire the `hello_handler` for the event `'my_event'`:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)
>>> manager.trigger_event("my_event")
Hello!
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): my_event
)

```

You can note that the last fired event name has been updated.
The current last fired event name is `'my_event'`.
The event manager uses the arguments that were given when the event handler was added.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler(first_name: str, last_name: str) -> None:
...     print(f"Hello. I am {first_name} {last_name}")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler, ('John', 'Smith')))
>>> manager.add_event_handler("my_event", EventHandler(hello_handler, ('Jane', 'Doe')))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ('John', 'Smith')
          (handler_kwargs): {}
        )
      (1): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ('Jane', 'Doe')
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)
>>> manager.trigger_event("my_event")
Hello. I am John Smith
Hello. I am Jane Doe

```

As explained above, it is possible to add a condition to control when to execute the handler.
The following shows how to execute the `hello_handler` every 3 `'my_event'` events.

```pycon
>>> from minevent import ConditionalEventHandler, PeriodicCondition, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3)))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): ConditionalEventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
          (condition): PeriodicCondition(freq=3, step=0)
        )
  (last_triggered_event): None
)
>>> for i in range(10):
...     print(f'i={i}')
...     manager.trigger_event("my_event")
...
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

### Remove an event handler

A previous section describes how to add an event handler, but sometimes it is useful to remove an
event handler.
The method `remove_event_handler` allows to remove an event handler from the event manager.
As explained above, the event handler is identified by an event name and a handler.
The following example shows how to add and remove an event handler:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
        (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)
>>> manager.remove_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
  (last_triggered_event): None
)

```

If there are multiple event handlers that match, they are all removed from the event manager:

```pycon
>>> from minevent import ConditionalEventHandler, PeriodicCondition, EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.add_event_handler("my_event", ConditionalEventHandler(hello_handler, PeriodicCondition(freq=3)))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
      (1): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
      (2): ConditionalEventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
          (condition): PeriodicCondition(freq=3, step=0)
        )
  (last_triggered_event): None
)
>>> manager.remove_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): ConditionalEventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
          (condition): PeriodicCondition(freq=3, step=0)
        )
  (last_triggered_event): None
)

```

If a handler is used for multiple events, only the handler associated to the event are removed:

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.add_event_handler("my_other_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
    (my_other_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)
>>> manager.remove_event_handler("my_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_other_event):
      (0): EventHandler(
          (handler): <function hello_handler at  0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)

```

A `RuntimeError` exception is raised if you try to remove an event handler that does not exist.

### Reset the event manager

It is possible to reset the event manager with the `reset` method. It removes all the event handlers
and set the last
fired event name to `None`. It is equivalent to create a new experiment manager.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager = EventManager()
>>> manager.add_event_handler("my_event", EventHandler(hello_handler))
>>> manager.add_event_handler("my_other_event", EventHandler(hello_handler))
>>> manager
EventManager(
  (event_handlers):
    (my_event):
      (0): EventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
    (my_other_event):
      (0): EventHandler(
          (handler): <function hello_handler at 0x...>
          (handler_args): ()
          (handler_kwargs): {}
        )
  (last_triggered_event): None
)
>>> manager.reset()
>>> manager
EventManager(
  (event_handlers):
  (last_triggered_event): None
)

```
