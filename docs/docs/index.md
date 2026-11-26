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

- **event** which is a case-sensitive string that names something that happens.
- **event handler** which is a callable to execute when the event happens.
- **event manager** (`EventManager`) which stores the event handlers and triggers the events.

A trigger can pass data to the handlers in a read-only `Context`, a condition can decide if a handler
runs, and each registration returns a `Subscription` that removes it. `minevent` has no dependency
and is fully typed.

A handler is a plain callable, so it can be tested without the event manager, and there is no base
class to extend.

!!! note "Version"

    The documentation of the `main` version describes the code of the `main` branch. Version `0.5.0`
    and older have a different API: use the version selector of their documentation, or see the
    [changelog](https://github.com/durandtibo/minevent/blob/main/CHANGELOG.md) to migrate.

## Motivation

`minevent` provides a minimal event system to customize a piece of code without changing its
implementation.
Below is an example on how to use `minevent` library.

```pycon
>>> from minevent import EventManager
>>> def say_something(manager: EventManager) -> None:
...     print("Hello, I am Bob!")
...     manager.trigger_event("after")
>>> manager = EventManager()
>>> say_something(manager)
Hello, I am Bob!
>>> def hello_handler(_) -> None:
...     print("Hello!")
>>> _ = manager.add_event_handler("after", hello_handler)
>>> say_something(manager)
Hello, I am Bob!
Hello!

```

It allows you to customize the function `say_something` without changing its implementation.

## Where to go next

| Page                            | Content                                              |
| ------------------------------- | ---------------------------------------------------- |
| [Get started](get_started.md)   | Install the library.                                 |
| [Quickstart](quickstart.md)     | The basics in a few minutes.                         |
| [Examples](examples.md)         | Recipes for training loops, plugins, async and tests |
| [User guide](guide.md)          | Recommendations, pitfalls and troubleshooting.       |
| [How it works](architecture.md) | The rules, the guarantees and the limits.            |
| [Design choices](design.md)     | Why it works this way, and the trade-offs.           |
| [Reference](refs/index.md)      | The classes and functions.                           |

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next. In fact, it is very likely that the API will change multiple times before a
stable 1.0.0 release. In practice, this means that upgrading `minevent` to a new version will
possibly break any code that was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available
in [LICENSE](https://github.com/durandtibo/minevent/blob/main/LICENSE) file.
