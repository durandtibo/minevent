# minevent

<p align="center">
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="CI" src="https://github.com/durandtibo/minevent/workflows/CI/badge.svg">
    </a>
    <a href="https://durandtibo.github.io/minevent/">
        <img alt="Documentation" src="https://github.com/durandtibo/minevent/workflows/Documentation/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="Nightly Tests" src="https://github.com/durandtibo/minevent/workflows/Nightly%20Tests/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="Nightly Package Tests" src="https://github.com/durandtibo/minevent/workflows/Nightly%20Package%20Tests/badge.svg">
    </a>
    <br/>
    <a href="https://codecov.io/gh/durandtibo/minevent">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/minevent/branch/main/graph/badge.svg">
    </a>
    <a href="https://codeclimate.com/github/durandtibo/minevent/maintainability">
        <img src="https://api.codeclimate.com/v1/badges/140297b4dc048f952298/maintainability" />
    </a>
    <a href="https://codeclimate.com/github/durandtibo/minevent/test_coverage">
        <img src="https://api.codeclimate.com/v1/badges/140297b4dc048f952298/test_coverage" />
    </a>
    <br/>
    <a href="https://pypi.org/project/minevent/">
        <img alt="PYPI version" src="https://img.shields.io/pypi/v/minevent">
    </a>
    <a href="https://pypi.org/project/minevent/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/minevent.svg">
    </a>
    <a href="https://opensource.org/licenses/BSD-3-Clause">
        <img alt="BSD-3-Clause" src="https://img.shields.io/pypi/l/minevent">
    </a>
    <a href="https://github.com/psf/black">
        <img  alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
    </a>
    <a href="https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings">
        <img  alt="Doc style: google" src="https://img.shields.io/badge/%20style-google-3666d6.svg">
    </a>
    <br/>
    <a href="https://pepy.tech/project/minevent">
        <img  alt="Downloads" src="https://static.pepy.tech/badge/minevent">
    </a>
    <a href="https://pepy.tech/project/minevent">
        <img  alt="Monthly downloads" src="https://static.pepy.tech/badge/minevent/month">
    </a>
    <br/>
</p>

## Overview

`minevent` is a Python library that provides a minimal event system for Machine Learning.
It allows to customize a code by adding some piece of code that are executed when an event is
fired.
`minevent` is organized around three main concepts:

- **event** which defines the thing that should happen.
- **event handler** which is the piece of code to execute when the event happens
- **event manager** which is responsible to manage the events and event handlers.

The library provides some implemented modules, but it is possible to extend it.
It is possible to use all the components or just a subset based on the need.
For example, an event handler can be used without the event manager.

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
>>> from minevent import EventHandler, EventManager
>>> def say_something(manager: EventManager) -> None:
...     print("Hello, I am Bob!")
...     manager.trigger_event("after")
...
>>> manager = EventManager()
>>> say_something(manager)
Hello, I am Bob!
>>> def hello_handler() -> None:
...     print("Hello!")
...
>>> manager.add_event_handler("after", EventHandler(hello_handler))
>>> say_something(manager)
Hello, I am Bob!
Hello!

```

It allows to customize the function `say_something` without changing its implementation.
Please read the [quickstart page](https://durandtibo.github.io/minevent/quickstart/) to learn more
about the library.

## Installation

We highly recommend installing
a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).
`minevent` can be installed from pip using the following command:

```shell
pip install minevent
```

To make the package as slim as possible, only the minimal packages required to use `minevent` are
installed.
To include all the dependencies, you can use the following command:

```shell
pip install minevent[all]
```

Please check the [get started page](https://durandtibo.github.io/minevent/get_started) to see how to
install only some specific dependencies or other alternatives to install the library.
The following is the corresponding `minevent` versions and supported dependencies.

| `minevent` | `coola`            | `python`      |
|------------|--------------------|---------------|
| `main`     | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.5`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.4`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.3`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.2`    | `>=0.0.20,<0.0.23` | `>=3.9,<3.12` |
| `0.0.1`    | `>=0.0.20,<0.0.23` | `>=3.9,<3.12` |

## Contributing

Please check the instructions in [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next.
In fact, it is very likely that the API will change multiple times before a stable 1.0.0 release.
In practice, this means that upgrading `minevent` to a new version will possibly break any code that
was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available in [LICENSE](LICENSE)
file.
