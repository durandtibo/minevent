# minevent

<p align="center">
    <a href="https://github.com/durandtibo/minevent/actions/workflows/ci.yaml">
        <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/durandtibo/minevent/ci.yaml?branch=main&label=CI&logo=github"></a>
    <a href="https://github.com/durandtibo/minevent/actions/workflows/nightly-package.yaml">
        <img alt="Nightly Package Tests" src="https://img.shields.io/github/actions/workflow/status/durandtibo/minevent/nightly-package.yaml?label=nightly&logo=github"></a>
    <a href="https://codecov.io/gh/durandtibo/minevent">
        <img alt="Codecov" src="https://img.shields.io/codecov/c/github/durandtibo/minevent?logo=codecov"></a>
    <a href="https://durandtibo.github.io/minevent/">
        <img alt="Documentation (stable)" src="https://img.shields.io/badge/docs-stable-blue?logo=readthedocs&logoColor=white"></a>
    <br/>
    <a href="https://pypi.org/project/minevent/">
        <img alt="PyPI version" src="https://img.shields.io/pypi/v/minevent?logo=pypi&logoColor=white"></a>
    <a href="https://pypi.org/project/minevent/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/minevent?logo=python&logoColor=white"></a>
    <a href="https://opensource.org/licenses/BSD-3-Clause">
        <img alt="BSD-3-Clause" src="https://img.shields.io/pypi/l/minevent"></a>
    <br/>
    <a href="https://github.com/astral-sh/ruff">
        <img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
    <a href="https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings">
        <img alt="Doc style: google" src="https://img.shields.io/badge/docstyle-google-3666d6"></a>
    <a href="https://scorecard.dev/viewer/?uri=github.com/durandtibo/minevent">
        <img alt="OpenSSF Scorecard" src="https://img.shields.io/ossf-scorecard/github.com/durandtibo/minevent?label=openssf%20scorecard"></a>
    <br/>
    <a href="https://pepy.tech/project/minevent">
        <img alt="Downloads" src="https://img.shields.io/pepy/dt/minevent"></a>
    <a href="https://pepy.tech/project/minevent">
        <img alt="Monthly downloads" src="https://img.shields.io/pepy/dm/minevent"></a>
    <a href="https://github.com/durandtibo/minevent/stargazers">
        <img alt="GitHub stars" src="https://img.shields.io/github/stars/durandtibo/minevent?logo=github"></a>
</p>

## Overview

`minevent` is a Python library that provides a minimal event system for Machine Learning.
It allows you to customize code by adding pieces of code that are executed when an event is
fired.
`minevent` is organized around three main concepts:

- **event** which is a case-sensitive string that names something that happens.
- **event handler** which is a callable to execute when the event happens.
- **event manager** (`EventManager`) which stores the event handlers and triggers the events.

The library provides a built-in condition (`PeriodicCondition`) to control when a handler runs, and
it is easy to extend: a handler is a callable and a condition is any
function that returns a boolean, so there is no base class to extend.
It is possible to use all the components or just a subset based on the need.
For example, a handler is a plain callable, so it can be tested without the event manager.

- [Features](#features)
- [Usage](#usage)
- [Documentation](#documentation)
- [Installation](#installation)
- [Contributing](#contributing)
- [Community and support](#community-and-support)
- [API stability](#api-stability)
- [License](#license)

:information_source: This page describes the `main` branch. Version `0.5.0` and older have a
different API: see [Installation](#installation).

## Features

- **No dependency**, standard library only
- **Plain callables** as handlers, called with no argument or with the data of the trigger
- **Read-only payload**: the data of a trigger is shared in an immutable `Context`
- **Conditions** to control when a handler runs, with `PeriodicCondition` or any function that
  returns a boolean
- **Registrations** that run once, are removed with their `Subscription`, or are scoped with a
  `with` block
- **Coroutine handlers** with `atrigger_event`
- **Predictable dispatch**: registration order, fail-fast errors with a note that names the handler,
  and a thread-safe registry
- **Fully typed**

## Usage

### Register a handler and trigger an event

A handler is a callable that needs no argument or only the context, which holds the data of the
trigger:

```pycon
>>> from minevent import Context, EventManager
>>> manager = EventManager()
>>> @manager.on("epoch_end")
... def log_epoch(context: Context) -> None:
...     print(f"epoch {context['epoch']}, loss {context.get('loss', 'unknown')}")
>>> _ = manager.add_event_handler("epoch_end", lambda: print("done"))
>>> manager.trigger_event("epoch_end", {"epoch": 1, "loss": 0.5})
epoch 1, loss 0.5
done

```

The handlers of an event run one after the other, in the order they were added. `context["epoch"]`
reads a required value, and `context.get("loss", default)` an optional one.

### Control when a handler runs

A condition is a function that returns a boolean. It can read the data of the trigger too. With
`once=True`, a handler runs at most once:

```pycon
>>> from minevent import EventManager, PeriodicCondition
>>> manager = EventManager()
>>> _ = manager.add_event_handler(
...     "epoch_end", lambda: print("checkpoint"), condition=PeriodicCondition(freq=2)
... )
>>> _ = manager.add_event_handler(
...     "epoch_end",
...     lambda context: print(f"late epoch {context['epoch']}"),
...     condition=lambda context: context["epoch"] >= 2,
... )
>>> _ = manager.add_event_handler("epoch_end", lambda: print("first epoch"), once=True)
>>> for epoch in range(3):
...     manager.trigger_event("epoch_end", {"epoch": epoch})
checkpoint
first epoch
checkpoint
late epoch 2

```

### Remove a handler

`add_event_handler` returns the `Subscription` of the registration:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> subscription = manager.add_event_handler("batch_end", lambda: print("batch"))
>>> subscription.remove()
True
>>> with manager.add_event_handler("batch_end", lambda: print("profiling")):
...     manager.trigger_event("batch_end")
profiling
>>> len(manager)
0

```

`manager.clear_event("batch_end")` removes the handlers of an event, and `manager.reset()` removes
all of them.

### Use coroutine handlers

```pycon
>>> import asyncio
>>> from minevent import Context, EventManager
>>> async def upload(context: Context) -> None:
...     print(f"upload epoch {context['epoch']}")
>>> manager = EventManager()
>>> _ = manager.add_event_handler("epoch_end", upload)
>>> asyncio.run(manager.atrigger_event("epoch_end", {"epoch": 1}))
upload epoch 1

```

### Which callables can be handlers

The parameters that have a default are ignored. A callable is then called as `f()` if no parameter
is left, and as `f(context)` if exactly one positional parameter is left. Anything else raises a
`TypeError` at registration, including `*args` and `**kwargs`, so wrap a callable such as `print` in
a lambda, or bind its arguments with `functools.partial`. See
[the calling rule](https://durandtibo.github.io/minevent/main/architecture/#the-calling-rule).

## Documentation

The [documentation of the `main` branch](https://durandtibo.github.io/minevent/main/) has the
following pages:

- [Quickstart](https://durandtibo.github.io/minevent/main/quickstart/): the first contact
- [Examples](https://durandtibo.github.io/minevent/main/examples/): runnable recipes
- [User guide](https://durandtibo.github.io/minevent/main/guide/): recommendations and
  troubleshooting
- [How it works](https://durandtibo.github.io/minevent/main/architecture/): the rules, the
  guarantees and the limits
- [Design choices](https://durandtibo.github.io/minevent/main/design/): the reasons and the
  trade-offs
- [Reference](https://durandtibo.github.io/minevent/main/refs/): the classes and their arguments

The [documentation of the latest release](https://durandtibo.github.io/minevent/latest/) is also
available.

## Installation

We highly recommend installing
a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).
`minevent` can be installed from pip using the following command:

```shell
pip install minevent
```

`minevent` has no dependency, so no optional dependencies or extras are required. It supports Linux
and macOS: Windows is not supported.

This command installs the latest release. To use the API described on this page before it is
released, install the `main` branch:

```shell
pip install git+https://github.com/durandtibo/minevent.git
```

Please check the [get started page](https://durandtibo.github.io/minevent/main/get_started/) for
other alternatives to install the library.
The following is the corresponding `minevent` versions and supported Python versions. The older
versions are listed on the [releases page](https://github.com/durandtibo/minevent/releases) and
the changes, with the migration from `0.5.0`, are listed in the
[changelog](https://github.com/durandtibo/minevent/blob/main/CHANGELOG.md).

| `minevent` | `python` |
| ---------- | -------- |
| `main`     | `>=3.11` |
| `0.5.0`    | `>=3.10` |
| `0.4.0`    | `>=3.10` |

## Contributing

We welcome contributions from the community! Whether you're fixing bugs, adding features, improving
documentation, or creating examples, your help is appreciated.

### How to Contribute

1. **Report Issues**: Found a bug? Have a feature request? Open an issue on GitHub
2. **Submit Pull Requests**: Fix bugs or add features by submitting a PR
3. **Improve Documentation**: Help make our docs better
4. **Share Examples**: Create examples showing how you use `minevent`

Please check the instructions in
[CONTRIBUTING.md](https://github.com/durandtibo/minevent/blob/main/CONTRIBUTING.md)
for detailed information.

## Community and Support

- **Issues**: [GitHub Issue Tracker](https://github.com/durandtibo/minevent/issues)
- **Discussions**: Use GitHub Discussions for questions and community interaction
- **Security**: See
  [SECURITY.md](https://github.com/durandtibo/minevent/blob/main/SECURITY.md)
  for security policy and reporting vulnerabilities

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next.
In fact, it is very likely that the API will change multiple times before a stable 1.0.0 release.
In practice, this means that upgrading `minevent` to a new version will possibly break any code that
was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available in [LICENSE](https://github.com/durandtibo/minevent/blob/main/LICENSE)
file.
