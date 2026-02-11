Welcome to POCS documentation!
==============================

<p align="center">
<img src="https://1730110767-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FDWxHUx4DyP5m2IEPanYp%2Fuploads%2FgQCffci1IsQlxhwQxspc%2FPAN001.png?alt=media&token=3b6a7fc1-efc1-416d-863b-d23304a6c28b" alt="PAN001" />
</p>
<br>

[![GHA Status](https://github.com/panoptes/POCS/actions/workflows/pythontest.yaml/badge.svg?branch=develop)](https://github.com/panoptes/POCS/actions/workflows/pythontest.yaml)
[![codecov](https://codecov.io/gh/panoptes/POCS/graph/badge.svg?token=0FGBB0iVy6)](https://codecov.io/gh/panoptes/POCS)
[![Documentation Status](https://readthedocs.org/projects/pocs/badge/?version=latest)](https://pocs.readthedocs.io/en/latest/?badge=latest) 
[![PyPI version](https://badge.fury.io/py/panoptes-pocs.svg)](https://badge.fury.io/py/panoptes-pocs)

# Project PANOPTES

[PANOPTES](https://www.projectpanoptes.org) is an open source citizen science project
designed to find [transiting exoplanets](https://spaceplace.nasa.gov/transits/en/) with
digital cameras. The goal of PANOPTES is to establish a global network of of robotic
cameras run by amateur astronomers and schools (or anyone!) in order to monitor,
as continuously as possible, a very large number of stars. For more general information
about the project, including the science case and resources for interested individuals, see the
[project overview](https://projectpanoptes.org/articles/).

# POCS


POCS (PANOPTES Observatory Control System) is the main software driver for a
PANOPTES unit, responsible for high-level control of the unit.

For more information, see the full documentation at: https://pocs.readthedocs.io.

## Beginner Resources

New to POCS? Start here:

- **CLI Guide:** See [docs/cli-guide.md](docs/cli-guide.md) for complete command line reference
- **Command Line Examples:** Quick start at [examples/README.md](examples/README.md)
- **Conceptual Overview:** Read [docs/conceptual-overview.md](docs/conceptual-overview.md) to understand POCS without installing
- **Architecture Guide:** Read [docs/architecture-for-beginners.md](docs/architecture-for-beginners.md) to understand how POCS works  
- **Glossary:** Check [docs/glossary.md](docs/glossary.md) for definitions of all terms
- **Python Examples:** Run [examples/beginner_simulation.py](examples/beginner_simulation.py) for API tutorial (advanced)

## Install

### POCS Environment

If you are running a PANOPTES unit then you will most likely want an  entire PANOPTES environment, which includes the necessary tools for operation of a complete unit.

There is a bash shell script that will install an entire working POCS system on your computer.  Some
folks even report that it works on a Mac.

To install POCS via the script, open a terminal and enter (you may be prompted for your `sudo` password):

```bash
curl -fsSL https://install.projectpanoptes.org > install.sh
bash install.sh
```

Or using `wget`:

```bash
wget -qO- https://install.projectpanoptes.org > install.sh
bash install.sh
```

The install script will ask a few questions at the beginning of the process. If you are unsure of 
the answer the default is probably okay.

In addition to installing `POCS`, the install script will create the Config Server
and Power Monitor services, which will automatically  be restarted upon reboot of the computer.


### POCS Module

If you want just the POCS module, for instance if you want to override it in
your own OCS (see [Huntsman-POCS](https://github.com/AstroHuntsman/huntsman-pocs)
for an example), then install via `pip`:

```bash
pip install panoptes-pocs
```

If you want the extra features, such as Google Cloud Platform connectivity, then
use the extras options:

```bash
pip install "panoptes-pocs[google,focuser,testing]"
```

#### Running POCS

`POCS` requires a few things to properly run:

1. A [`panoptes-utils`](https://github.com/panoptes/panoptes-utils.git) `config-server` running to provide dynamic configuration.
2. An `Observatory` instance that has details about the location of a POCS unit (real or simulated), which hardware is available, etc.

A minimal working example with a simulated `Observatory` would be:

```python
import os
from panoptes.utils.config.server import config_server
from panoptes.pocs.core import POCS

os.environ['PANDIR'] = '/var/panoptes'
conf_server = config_server('conf_files/pocs.yaml')
I 01-20 01:01:10.886 Starting panoptes-config-server with  config_file='conf_files/pocs.yaml'
S 01-20 01:01:10.926 Config server Loaded 17 top-level items
I 01-20 01:01:10.928 Config items saved to flask config-server
I 01-20 01:01:10.934 Starting panoptes config server with localhost:6563

pocs = POCS.from_config(simulators=['all'])
I 01-20 01:01:20.408 Initializing PANOPTES unit - Generic PANOPTES Unit - Mauna Loa Observatory
I 01-20 01:01:20.419 Making a POCS state machine from panoptes
I 01-20 01:01:20.420 Loading state table: panoptes
S 01-20 01:01:20.485 Unit says: Hi there!
W 01-20 01:01:20.494 Scheduler not present
W 01-20 01:01:20.495 Cameras not present
W 01-20 01:01:20.496 Mount not present
I 01-20 01:01:20.497 Scheduler not present, cannot get current observation.

pocs.initialize()
W 01-20 01:01:28.386 Scheduler not present
W 01-20 01:01:28.388 Cameras not present
W 01-20 01:01:28.389 Mount not present
S 01-20 01:01:28.390 Unit says: Looks like we're missing some required hardware.
Out[10]: False
```

For a more realistic usage, see the full documentation at: [https://pocs.readthedocs.io](https://pocs.readthedocs.io).

For actually deploying a PANOPTES unit, refer to the [Operating Guide](https://projectpanoptes.gitbook.io/pocs-user-guide/operation/operating-guides).

#### Using POCS

POCS provides a command line interface for all operations. After installation:

**1. Configure your unit (required first step):**
```bash
pocs config setup
```

**2. Run automated observing:**
```bash
pocs run auto
```

**3. Manual hardware control:**
```bash
# Mount control
pocs mount slew-to-target --target M42
pocs mount park

# Camera testing
pocs camera take-pics --num-images 5 --exptime 2.0
```

For more CLI commands, run `pocs --help` or see the beginner documentation above.

#### Developing POCS

See [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES)

### Development with Hatch

This project uses UV for fast Python package and environment management.

Prerequisites:
- Python 3.12+
- UV: https://docs.astral.sh/uv/ (install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `pipx install uv`).

Basic workflow:

- Create and sync a dev environment with all dependencies:
  ```bash
  # Install all optional extras (recommended for development)
  uv sync --all-extras
  
  # Or install only base dependencies
  uv sync
  
  # Activate the virtual environment
  source .venv/bin/activate
  # or run commands without activating using `uv run ...`
  ```

- Install specific optional extras as needed (choose any):
  ```bash
  # Examples: google, focuser, weather, testing
  uv sync --extra google --extra focuser --extra weather --extra testing
  
  # Or install the 'all' extra which includes everything
  uv sync --extra all
  ```

- Run tests:
  ```bash
  # All tests with coverage, using pytest options from pyproject.toml
  uv run pytest

  # Single test file
  uv run pytest tests/test_mount.py
  ```

- Lint / style checks:
  ```bash
  # Lint (Ruff)
  hatch run lint
  # Format (Ruff)
  hatch run fmt
  # Check formatting without changes
  hatch run fmt-check
  ```

- Build the package (wheel and sdist):
  ```bash
  hatch build
  ```

- Run the CLI locally (Typer app):
  ```bash
  hatch run pocs --help
  ```

- Versioning:
  Version is derived from git tags via hatch-vcs. To produce a new version, create and push a tag (e.g., `v0.1.0`).

#### [Testing]

To test the software, prefer running via Hatch so the right environment and options are used:

```bash
hatch run pytest
```

By default all tests will be run. If you want to run one specific test, give the specific filename as an argument to `pytest`:

```bash
hatch run pytest tests/test_mount.py
```

Links
-----

- PANOPTES Homepage: https://www.projectpanoptes.org
- Forum: https://forum.projectpanoptes.org
- Documentation: https://pocs.readthedocs.io
- Source Code: https://github.com/panoptes/POCS

[Testing]: #testing
