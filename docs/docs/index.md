# Home

<p align="center">
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="CI" src="https://github.com/durandtibo/minevent/workflows/CI/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="Nightly Tests" src="https://github.com/durandtibo/minevent/workflows/Nightly%20Tests/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions">
        <img alt="Nightly Package Tests" src="https://github.com/durandtibo/minevent/workflows/Nightly%20Package%20Tests/badge.svg">
    </a>
    <a href="https://codecov.io/gh/durandtibo/minevent">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/minevent/branch/main/graph/badge.svg">
    </a>
    <br/>
    <a href="https://durandtibo.github.io/minevent/">
        <img alt="Documentation" src="https://github.com/durandtibo/minevent/workflows/Documentation%20(stable)/badge.svg">
    </a>
    <a href="https://durandtibo.github.io/minevent/">
        <img alt="Documentation" src="https://github.com/durandtibo/minevent/workflows/Documentation%20(unstable)/badge.svg">
    </a>
    <br/>
    <a href="https://github.com/psf/black">
        <img  alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
    </a>
    <a href="https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings">
        <img  alt="Doc style: google" src="https://img.shields.io/badge/%20style-google-3666d6.svg">
    </a>
    <a href="https://github.com/astral-sh/ruff">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" style="max-width:100%;">
    </a>
    <a href="https://github.com/guilatrova/tryceratops">
        <img  alt="Doc style: google" src="https://img.shields.io/badge/try%2Fexcept%20style-tryceratops%20%F0%9F%A6%96%E2%9C%A8-black">
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
Please read the [quickstart page](quickstart.md) to learn more about the library.

## API stability

:warning: While `minevent` is in development stage, no API is guaranteed to be stable from one
release to the next. In fact, it is very likely that the API will change multiple times before a
stable 1.0.0 release. In practice, this means that upgrading `minevent` to a new version will
possibly break any code that was using the old version of `minevent`.

## License

`minevent` is licensed under BSD 3-Clause "New" or "Revised" license available
in [LICENSE](https://github.com/durandtibo/minevent/blob/main/LICENSE) file.
