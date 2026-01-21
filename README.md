# minevent

<p align="center">
    <a href="https://github.com/durandtibo/minevent/actions/workflows/ci.yaml">
        <img alt="CI" src="https://github.com/durandtibo/minevent/actions/workflows/ci.yaml/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions/workflows/nightly-tests.yaml">
        <img alt="Nightly Tests" src="https://github.com/durandtibo/minevent/actions/workflows/nightly-tests.yaml/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/minevent/actions/workflows/nightly-package.yaml">
        <img alt="Nightly Package Tests" src="https://github.com/durandtibo/minevent/actions/workflows/nightly-package.yaml/badge.svg">
    </a>
    <a href="https://codecov.io/gh/durandtibo/minevent">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/minevent/branch/main/graph/badge.svg">
    </a>
    <br/>
    <a href="https://durandtibo.github.io/minevent/">
        <img alt="Documentation" src="https://github.com/durandtibo/minevent/actions/workflows/docs.yaml/badge.svg">
    </a>
    <a href="https://durandtibo.github.io/minevent/dev/">
        <img alt="Documentation" src="https://github.com/durandtibo/minevent/actions/workflows/docs-dev.yaml/badge.svg">
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

## Features

- **Minimal and Lightweight**: Only depends on `coola`, keeping your project dependencies clean
- **Simple API**: Easy to learn and use with intuitive event registration and triggering
- **Conditional Handlers**: Built-in support for conditional event execution (e.g., periodic
  execution)
- **Extensible**: Create custom event handlers and conditions for your specific needs
- **Type Hints**: Full type hint support for better IDE integration and code quality
- **Well Tested**: Comprehensive test suite ensuring reliability
- **Well Documented**: Extensive documentation with examples and best practices

## Quick Links

- **Documentation**:
  [https://durandtibo.github.io/minevent/](https://durandtibo.github.io/minevent/)
- **Quickstart Guide**:
  [https://durandtibo.github.io/minevent/quickstart/](https://durandtibo.github.io/minevent/quickstart/)
- **Examples**: See the [`examples/`](examples/) directory for practical use cases
- **FAQ**: [https://durandtibo.github.io/minevent/faq/](https://durandtibo.github.io/minevent/faq/)
- **Best Practices**:
  [https://durandtibo.github.io/minevent/best_practices/](https://durandtibo.github.io/minevent/best_practices/)

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

| `minevent` | `coola`         | `python`       |
|------------|-----------------|----------------|
| `main`     | `>=1.0,<2.0`    | `>=3.10`       |
| `0.5.0`    | `>=1.0,<2.0`    | `>=3.10`       |
| `0.4.0`    | `>=0.10,<1.0`   | `>=3.10`       |
| `0.3.2`    | `>=0.9.1,<1.0`  | `>=3.10,<3.15` |
| `0.3.1`    | `>=0.8.4,<1.0`  | `>=3.9,<3.14`  |
| `0.3.0`    | `>=0.1,<1.0`    | `>=3.9,<3.13`  |
| `0.2.1`    | `>=0.1,<0.3`    | `>=3.9,<3.13`  |
| `0.2.0`    | `>=0.1,<0.3`    | `>=3.9,<3.13`  |
| `0.1.0`    | `>=0.0.20,<0.2` | `>=3.9,<3.13`  |

<details>
    <summary>older versions</summary>

| `minevent` | `coola`            | `python`      |
|------------|--------------------|---------------|
| `0.0.5`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.4`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.3`    | `>=0.0.20,<0.0.24` | `>=3.9,<3.12` |
| `0.0.2`    | `>=0.0.20,<0.0.23` | `>=3.9,<3.12` |
| `0.0.1`    | `>=0.0.20,<0.0.23` | `>=3.9,<3.12` |

</details>

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
