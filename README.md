Welcome to POCS documentation!
==============================

<p align="center">
<img src="https://1730110767-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FDWxHUx4DyP5m2IEPanYp%2Fuploads%2FgQCffci1IsQlxhwQxspc%2FPAN001.png?alt=media&token=3b6a7fc1-efc1-416d-863b-d23304a6c28b" alt="PAN001" />
</p>
<br>

[![GHA Status](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Factions-badge.atrox.dev%2Fpanoptes%2FPOCS%2Fbadge%3Fref%3Ddevelop&style=flat)](https://actions-badge.atrox.dev/panoptes/POCS/goto?ref=develop) [![codecov](https://codecov.io/gh/panoptes/POCS/branch/develop/graph/badge.svg)](https://codecov.io/gh/panoptes/POCS) [![Documentation Status](https://readthedocs.org/projects/pocs/badge/?version=latest)](https://pocs.readthedocs.io/en/latest/?badge=latest) [![PyPI version](https://badge.fury.io/py/panoptes-pocs.svg)](https://badge.fury.io/py/panoptes-pocs)

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

## Install

### POCS Environment

If you are running a PANOPTES unit then you will most likely want an  entire PANOPTES environment, which includes the necessary tools for operation of a complete unit.

There is a bash shell script that will install an entire working POCS system on your computer.  Some
folks even report that it works on a Mac.

To install POCS via the script, open a terminal and enter (you may be prompted for your `sudo` password):

```bash
curl -fsSL https://install.projectpanoptes.org > install-pocs.sh
bash install-pocs.sh
```

Or using `wget`:

```bash
wget -qO- https://install.projectpanoptes.org > install-pocs.sh
bash install-pocs.sh
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
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.core import POCS

os.environ['PANDIR'] = '/var/panoptes'
conf_server = config_server('conf_files/pocs.yaml')
I 01-20 01:01:10.886 Starting panoptes-config-server with  config_file='conf_files/pocs.yaml'
S 01-20 01:01:10.926 Config server Loaded 17 top-level items
I 01-20 01:01:10.928 Config items saved to flask config-server
I 01-20 01:01:10.934 Starting panoptes config server with localhost:6563

observatory = Observatory()
I 01-20 01:01:16.157 Creating PanDB panoptes
I 01-20 01:01:16.158 Initializing observatory
I 01-20 01:01:16.158 Setting up location
S 01-20 01:01:17.070 Observatory initialized

pocs = POCS(observatory, simulators=['all'])
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

For actually deploying a PANOPTES unit, refer to the [Operating Guider](https://projectpanoptes.gitbook.io/pocs-user-guide/operation/operating-guides).

#### Developing POCS

See [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES)

#### [Testing]

To test the software, you can use the standard `pytest` tool from the root of the directory.
 
By default all tests will be run. If you want to run one specific test, give the specific filename as an argument to `pytest`:

```bash
pytest tests/test_mount.py
```

Links
-----

- PANOPTES Homepage: https://www.projectpanoptes.org
- Forum: https://forum.projectpanoptes.org
- Documentation: https://pocs.readthedocs.io
- Source Code: https://github.com/panoptes/POCS

[Testing]: #testing
