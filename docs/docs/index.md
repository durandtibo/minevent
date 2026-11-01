# Home

[![CI](https://github.com/durandtibo/minevent/actions/workflows/ci.yaml/badge.svg)](https://github.com/durandtibo/minevent/actions/workflows/ci.yaml)
[![PyPI version](https://img.shields.io/pypi/v/minevent)](https://pypi.org/project/minevent/)
[![Python](https://img.shields.io/pypi/pyversions/minevent.svg)](https://pypi.org/project/minevent/)
[![BSD-3-Clause](https://img.shields.io/pypi/l/minevent)](https://opensource.org/licenses/BSD-3-Clause)

The full list of badges, the installation instructions and the version table are in the
[README](https://github.com/durandtibo/minevent#readme).

## Overview

`minevent` is a Python library that provides a minimal event system for Machine Learning.
It allows you to customize code by adding pieces of code that are executed when an event is
fired.
`minevent` is organized around three main concepts:

- **event** which defines the thing that should happen.
- **event handler** which is the piece of code to execute when the event happens
- **event manager** which is responsible to manage the events and event handlers.

The goal of this documentation is to explain how the event system works and how to use it.
The library provides some implemented modules, but it is possible to extend it.
It is possible to use all the components or just a subset based on the need.
For example, an event handler can be used without the event manager.

## Motivation

`minevent` provides a minimal event system to customize a piece of code without changing its
implementation.
Below is an example on how to use `minevent` library.

```pycon
>>> from minevent import EventHandler, EventManager
>>> def say_something(manager: EventManager) -> None:
...     print("Hello, I am Bob!")
...     manager.trigger_event("after")
>>> manager = EventManager()
>>> say_something(manager)
Hello, I am Bob!
>>> def hello_handler() -> None:
...     print("Hello!")
>>> _ = manager.add_event_handler("after", EventHandler(hello_handler))
>>> say_something(manager)
Hello, I am Bob!
Hello!

```

It allows you to customize the function `say_something` without changing its implementation.
Please read the [quickstart page](quickstart.md) to learn more about the library.

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next. In fact, it is very likely that the API will change multiple times before a
stable 1.0.0 release. In practice, this means that upgrading `minevent` to a new version will
possibly break any code that was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available
in [LICENSE](https://github.com/durandtibo/minevent/blob/main/LICENSE) file.
