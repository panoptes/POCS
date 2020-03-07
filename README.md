# PANOPTES Observatory Control System

<p align="center">
<img src="https://projectpanoptes.org/uploads/2018/12/16/pan-logo.png" alt="PANOPTES logo" style="border: 1px solid;" width="400px" />  
</p>
<br>

[![Build Status](https://travis-ci.org/panoptes/POCS.svg?branch=develop)](https://travis-ci.org/panoptes/POCS)
[![codecov](https://codecov.io/gh/panoptes/POCS/branch/develop/graph/badge.svg)](https://codecov.io/gh/panoptes/POCS)
[![astropy](http://img.shields.io/badge/powered%20by-AstroPy-orange.svg?style=flat)](http://www.astropy.org/)

- [PANOPTES Observatory Control System](#panoptes-observatory-control-system)
  - [Overview](#overview)
  - [Getting Started](#getting-started)
  - [Setup](#setup)
    - [Install Script](#install-script)
  - [Test POCS](#test-pocs)
    - [Software Testing](#software-testing)
      - [Testing your installation](#testing-your-installation)
      - [Testing your code changes](#testing-your-code-changes)
      - [Writing tests](#writing-tests)
    - [Hardware Testing](#hardware-testing)
  - [Links](#links)

## Overview

[PANOPTES](https://projectpanoptes.org) is an open source citizen science project
that is designed to find exoplanets with digital cameras. The goal of PANOPTES is
to establish a global network of of robotic cameras run by amateur astronomers
and schools in order to monitor, as continuously as possible, a very large number
of stars. For more general information about the project, including the science
case and resources for interested individuals, see the
[about page](https://projectpanoptes.org/articles/what-is-panoptes/).

POCS (PANOPTES Observatory Control System) is the main software driver for the
PANOPTES unit, responsible for high-level control of the unit. There are also
files for a one-time upload to the arduino hardware, as well as various scripts
to read information from the environmental sensors.

## Getting Started

POCS is designed to control a fully constructed PANOPTES unit.  Additionally,
POCS can be run with simulators when hardware is not present or when the system
is being developed.

For information on building a PANOPTES unit, see the main [PANOPTES](https://projectpanoptes.org) website and join the [community forum](https://forum.projectpanoptes.org).

To get started with POCS there are three easy steps:

1. **Setup** POCS on the computer you will be using for your unit or for development.
2. **Test** your POCS setup by running our testing script
3. **Start using POCS!**

See below for more details.

## Setup

### Install Script

## Test POCS

POCS comes with a testing suite that allows it to test that all of the software
works and is installed correctly. Running the test suite by default will use simulators for all of the hardware and is meant to test that the software works correctly. Additionally, the testing suite can be run with various flags to test that attached hardware is working properly.

### Software Testing

There are a few scenarios where you want to run the test suite:

1. You are getting your unit ready and want to test software is installed correctly.
2. You are upgrading to a new release of software (POCS, its dependencies or the operating system).
3. You are helping develop code for POCS and want test your code doesn't break something.

#### Testing your installation

In order to test your installation you should have followed all of the steps above
for getting your unit ready. To run the test suite, you will need to open a terminal
and navigate to the `$POCS` directory.

```bash
cd $POCS

# Run the software testing
scripts/testing/test-software.sh
```

> :bulb: NOTE: The test suite will give you some warnings about what is going on and give you a chance to cancel the tests (via `Ctrl-c`).

It is often helpful to view the log output in another terminal window while the test suite is running:

```bash
# Follow the log file
$ tail -F $PANDIR/logs/panoptes.log
```

#### Testing your code changes

> :bulb: NOTE: This step is meant for people helping with software development.

The testing suite will automatically be run against any code committed to our github
repositories. However, the test suite should also be run locally before pushing
to github. This can be done either by running the entire test suite as above or
by running an individual test related to the code you are changing. For instance,
to test the code related to the cameras one can run:

```bash
(panoptes-env) $ pytest -xv pocs/tests/test_camera.py
```

Here the `-x` option will stop the tests upon the first failure and the `-v` makes
the testing verbose.

Note that some tests might require additional software. This software is installed in the docker image, which is used by the `test-software.sh` script above), but is **not** used when calling `pytest` directly. For instance, anything requiring plate solving needs `astrometry.net` installed.

Any new code should also include proper tests. See below for details.

#### Writing tests

All code changes should include tests. We strive to maintain a high code coverage
and new code should necessarily maintain or increase code coverage.

For more details see the [Writing Tests](https://github.com/panoptes/POCS/wiki/Writing-Tests-for-POCS) page.

### Hardware Testing

Hardware testing uses the same testing suite as the software testing but with
additional options passed on the command line to signify what hardware should be
tested.

The options to pass to `pytest` is `--with-hardware`, which accepts a list of
possible hardware items that are connected. This list includes `camera`, `mount`,
and `weather`. Optionally you can use `all` to test a fully connected unit.

> :warning: The hardware tests do not perform safety checking of the weather or
> dark sky. The `weather` test mentioned above tests if a weather station is
> connected but does not test the safety conditions. It is assumed that hardware
> testing is always done with direct supervision.

```bash
# Test an attached camera
pytest --with-hardware=camera

# Test an attached camera and mount
pytest --with-hardware=camera,mount

# Test a fully connected unit
pytest --with-hardware=all
```

## Links

* PANOPTES Homepage: <https://projectpanoptes.org>
* Community Forum: <https://forum.projectpanoptes.org>
* Source Code: <https://github.com/panoptes/POCS>
