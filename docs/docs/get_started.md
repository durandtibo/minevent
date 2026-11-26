# Get Started

It is highly recommended to install in
a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/)
to keep your system in order.

## Installing with `pip` (recommended)

We highly recommend installing
a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).
`minevent` can be installed from pip using the following command:

```shell
pip install minevent
```

`minevent` has no dependency, so no optional dependencies or extras are required. It requires
Python 3.11 or newer on the `main` branch (see the
[version table](https://github.com/durandtibo/minevent#installation) for the releases). It supports
Linux and macOS: Windows is not supported.

This command installs the latest release. Version `0.5.0` and older have a different API than the
one of the `main` documentation. To install the code of the `main` branch:

```shell
pip install git+https://github.com/durandtibo/minevent.git
```

Check the installation:

```pycon
>>> from minevent import EventManager
>>> manager = EventManager()
>>> _ = manager.add_event_handler("hello", lambda: print("Hello!"))
>>> manager.trigger_event("hello")
Hello!

```

## Installing from source

To install `minevent` from source, you can follow the steps below.

### Prerequisites

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency management. If you don't have
`uv` installed, you can install it by following
the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Clone the repository

First, clone the git repository:

```shell
git clone https://github.com/durandtibo/minevent.git
cd minevent
```

### Install the dependencies

Create the virtual environment `.venv` with the package (in editable mode) and its development
dependencies, then activate it:

```shell
uv sync --python 3.13
source .venv/bin/activate
```

To also install the documentation dependencies, use `uv sync --python 3.13 --group docs`.

Once the environment is activated, `inv env.install` installs the dependencies again, and
`inv env.update` updates them. `inv --list` shows all the tasks.

### Verify the installation

Finally, you can test the installation by running the test suite:

```shell
inv test.unit --cov
```

## Development workflow

If you're planning to contribute to `minevent`, please refer to
the [Contributing Guide](https://github.com/durandtibo/minevent/blob/main/CONTRIBUTING.md)
for more information on setting up your development environment and running tests.
