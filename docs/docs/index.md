# Home

[![CI](https://github.com/durandtibo/minevent/actions/workflows/ci.yaml/badge.svg)](https://github.com/durandtibo/minevent/actions/workflows/ci.yaml)
[![PyPI version](https://img.shields.io/pypi/v/minevent)](https://pypi.org/project/minevent/)
[![Python](https://img.shields.io/pypi/pyversions/minevent.svg)](https://pypi.org/project/minevent/)
[![BSD-3-Clause](https://img.shields.io/pypi/l/minevent)](https://opensource.org/licenses/BSD-3-Clause)

The full list of badges and the version table are in the
[README](https://github.com/durandtibo/minevent#readme).

## Overview

`minevent` is a Python library that provides a minimal event system for Machine Learning.
It lets you customize a piece of code without changing it: the code announces what happens, and you
attach the code that must run at that moment.

For example, a training loop triggers `epoch_end`. Logging, checkpointing or monitoring is added by
registering a handler to that event, and the loop does not know about any of them.

`minevent` is organized around three main concepts:

- **event** which is a case-sensitive string that names something that happens.
- **event handler** which is a callable to execute when the event happens.
- **event manager** (`EventManager`) which stores the event handlers and triggers the events.

```text
your code                      EventManager                       your handlers
    |                    "epoch_end" -> [log, save]                     |
    |-- trigger_event("epoch_end", data) -->|-- log(context) ---------->|
    |                                       |-- save(context) --------->|
    |<--------------------------------------|   one after the other     |
```

## A first example

The function `say_something` triggers an event. Registering a handler changes what happens when the
function runs, without changing the function:

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

## What you can do

| You want to                           | Use                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------- |
| Pass data to the handlers             | [The payload of a trigger](quickstart.md#pass-data-to-the-handlers)    |
| Run a handler only sometimes, or once | [Conditions and `once`](quickstart.md#control-when-a-handler-runs)     |
| Remove a handler                      | [The `Subscription` of a registration](quickstart.md#remove-a-handler) |
| See what is registered                | [The registry](quickstart.md#look-at-the-registrations)                |
| Use `async def` handlers              | [`atrigger_event`](quickstart.md#coroutine-handlers)                   |
| Find which handler raised an error    | [The note of the exception](quickstart.md#errors)                      |

`minevent` has no dependency and is fully typed. A handler is a plain callable, so it can be tested
without the event manager, and there is no base class to extend. The library leaves out features
such as priorities, wildcards or background dispatch: see
[what is not provided](design.md#what-is-not-provided).

## Documentation

| Page                            | Content                                                |
| ------------------------------- | ------------------------------------------------------ |
| [Get started](get_started.md)   | Install the library.                                   |
| [Quickstart](quickstart.md)     | Each feature in a few minutes.                         |
| [Examples](examples.md)         | Recipes for training loops, plugins, async and tests.  |
| [User guide](guide.md)          | Recommendations and troubleshooting.                   |
| [How it works](architecture.md) | The parts, the rules, the guarantees and the limits.   |
| [Design choices](design.md)     | Why it works this way, and the trade-offs.             |
| [Reference](refs/index.md)      | The signatures and the docstrings of the public names. |

!!! note "Versions of the documentation"

    Each version of this documentation describes one version of `minevent`: `main` follows the `main`
    branch, and `latest` the latest release. Choose the one of your installed version with the version
    selector. The changes between the releases are in the
    [changelog](https://github.com/durandtibo/minevent/blob/main/CHANGELOG.md).

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next. In fact, it is very likely that the API will change multiple times before a
stable 1.0.0 release. In practice, this means that upgrading `minevent` to a new version will
possibly break any code that was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available
in [LICENSE](https://github.com/durandtibo/minevent/blob/main/LICENSE) file.
