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

- **event** which defines the thing that should happen.
- **event handler** which is any callable to execute when the event happens
- **event manager** which is responsible to manage the events and event handlers.

The library provides some implemented modules, but it is possible to extend it.
It is possible to use all the components or just a subset based on the need.
For example, a handler is a plain callable, so it can be tested without the event manager.

- [Motivation](#motivation)
- [Documentation](https://durandtibo.github.io/minevent/)
- [Installation](#installation)
- [Contributing](#contributing)
- [API stability](#api-stability)
- [License](#license)

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
>>> def hello_handler() -> None:
...     print("Hello!")
>>> _ = manager.add_event_handler("after", hello_handler)
>>> say_something(manager)
Hello, I am Bob!
Hello!

```

It allows you to customize the function `say_something` without changing its implementation.

## Features

- **Minimal and Lightweight**: No dependency, keeping your project dependencies clean
- **Simple API**: Easy to learn and use with intuitive event registration and triggering
- **Payload**: `trigger_event("epoch_end", epoch=3)` passes keyword arguments to the handlers
- **Subscriptions**: `add_event_handler` returns a `Subscription` to remove exactly that
  registration, and `once=True` runs a handler at most once
- **Conditional Handlers**: Any function that returns a boolean is a condition, and
  `PeriodicCondition` and `AfterNCondition` are provided
- **Async**: `atrigger_event` awaits coroutine handlers
- **Thread-safe registry**: register handlers and trigger events from different threads
- **Extensible**: A handler is any callable and a condition is any function that returns a boolean, so there is no base class to extend
- **Type Hints**: Full type hint support for better IDE integration and code quality
- **Well Tested**: Comprehensive test suite ensuring reliability
- **Well Documented**: Extensive documentation with examples and a user guide

## Quick Links

- **Documentation**:
  [https://durandtibo.github.io/minevent/](https://durandtibo.github.io/minevent/)
- **Quickstart Guide**:
  [https://durandtibo.github.io/minevent/quickstart/](https://durandtibo.github.io/minevent/quickstart/)
- **Examples**: See the [quickstart guide](https://durandtibo.github.io/minevent/quickstart/) for practical use cases
- **FAQ**: [https://durandtibo.github.io/minevent/faq/](https://durandtibo.github.io/minevent/faq/)
- **User guide**:
  [https://durandtibo.github.io/minevent/guide/](https://durandtibo.github.io/minevent/guide/)

## Installation

We highly recommend installing
a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).
`minevent` can be installed from pip using the following command:

```shell
pip install minevent
```

`minevent` has no dependency, so no optional dependencies or extras are required.

Please check the [get started page](https://durandtibo.github.io/minevent/get_started) for other
alternatives to install the library.
The following is the corresponding `minevent` versions and supported Python versions. The older
versions are listed on the [releases page](https://github.com/durandtibo/minevent/releases) and
the changes are listed in the [changelog](CHANGELOG.md).

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

Please check the instructions in [CONTRIBUTING.md](CONTRIBUTING.md) for detailed
information.

## Community and Support

- **Issues**: [GitHub Issue Tracker](https://github.com/durandtibo/minevent/issues)
- **Discussions**: Use GitHub Discussions for questions and community interaction
- **Security**: See [SECURITY.md](SECURITY.md) for security policy and reporting vulnerabilities

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next.
In fact, it is very likely that the API will change multiple times before a stable 1.0.0 release.
In practice, this means that upgrading `minevent` to a new version will possibly break any code that
was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available in [LICENSE](LICENSE)
file.
