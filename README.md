Welcome to POCS documentation!
==============================

<p align="center">
<img src="https://projectpanoptes.org/uploads/2018/12/16/PAN001_sunset.png" alt="PAN001" />  
</p>
<br>

[![GHA Status](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Factions-badge.atrox.dev%2Fpanoptes%2FPOCS%2Fbadge%3Fref%3Ddevelop&style=flat)](https://actions-badge.atrox.dev/panoptes/POCS/goto?ref=develop) [![Travis Status](https://travis-ci.com/panoptes/POCS.svg?branch=develop)](https://travis-ci.com/panoptes/POCS) [![codecov](https://codecov.io/gh/panoptes/POCS/branch/develop/graph/badge.svg)](https://codecov.io/gh/panoptes/POCS) [![Documentation Status](https://readthedocs.org/projects/panoptes-pocs/badge/?version=latest)](https://panoptes-pocs.readthedocs.io/en/latest/?badge=latest) [![PyPI version](https://badge.fury.io/py/panoptes-pocs.svg)](https://badge.fury.io/py/panoptes-pocs)

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

[`panoptes-utils`](https://www.github.com/panoptes/panoptes-utils) is a related repository and POCS
relies on most of the tools within `panoptes-utils`.

## Install

### POCS Environment

If you are running a PANOPTES unit then you will most likely want an entire PANOPTES environment.

There is a bash shell script that will install an entire working POCS system on your computer.  Some 
folks even report that it works on a Mac.

To test the script, open a terminal and enter:

```bash
curl -L https://install.projectpanoptes.org | bash
```

Or using `wget`:

```bash
wget -O - https://install.projectpanoptes.org | bash
```


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
pip install "panoptes-pocs[google,testing]"
```
   
See the full documentation at: https://pocs.readthedocs.io

### For helping develop POCS software

See [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES)

Links
-----

- PANOPTES Homepage: https://www.projectpanoptes.org
- Forum: https://forum.projectpanoptes.org
- Documentation: https://pocs.readthedocs.io
- Source Code: https://github.com/panoptes/POCS
