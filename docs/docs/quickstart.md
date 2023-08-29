# quickstart

This page presents the design used in `minevent`, but other designs exist.

## Overview

The `minevent` event system is composed of three main components:

- an event
- an event handler
- an event manager

It is a synchronous system i.e. only one event and event handler are executed at the same time.

## Event

In `minevent`, an event is a string that represents something happening.
The event is represented by the event name.
For example, it is possible to write the following line to define an event that happens after the
training is completed.

```python
my_event = "training completed"
```

## Event handler

In `minevent`, an event handler is a piece a code that is executed when an even happened.

An event handler must have two methods:

- `equal` which is used to compare two event handlers.
- `handle` which executes a piece of code when the event happens.

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