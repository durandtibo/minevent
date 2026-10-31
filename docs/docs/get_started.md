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

`minevent` only depends on [`coola`](https://github.com/durandtibo/coola), so no optional
dependencies or extras are required.

## Installing from source

To install `minevent` from source, you can follow the steps below.

### Prerequisites

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency management. If you don't have
`uv` installed, you can install it by following
the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Clone the repository

First, clone the git repository:

```shell
git clone git@github.com:durandtibo/minevent.git
cd minevent
```

### Create a virtual environment (optional but recommended)

It is recommended to create a Python 3.11+ virtual environment. You can use `uv` to create a virtual
environment:

```shell
uv venv --python 3.13
source .venv/bin/activate
```

### Install dependencies

Once you have activated your virtual environment, install the required packages with:

```shell
inv env.install
```

Or if you're developing and need documentation dependencies:

```shell
inv env.install --docs-deps
```

These commands will install all the required packages. You can also use these commands to update the
required packages.

### Verify the installation

Finally, you can test the installation by running the test suite:

```shell
inv test.unit --cov
```

## Development workflow

If you're planning to contribute to `minevent`, please refer to
the [Contributing Guide](https://github.com/durandtibo/minevent/blob/main/CONTRIBUTING.md)
for more information on setting up your development environment and running tests.
