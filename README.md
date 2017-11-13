Welcome to POCS documentation!
================================
<p align="center">
<img src="http://www.projectpanoptes.org/images/logo/png/sm/logo-inverted.png" alt="PANOPTES logo" style="border: 1px solid;" width="400px" />  
</p>
<br>

[![Build Status](https://travis-ci.org/panoptes/POCS.svg?branch=develop)](https://travis-ci.org/panoptes/POCS)
[![codecov](https://codecov.io/gh/panoptes/POCS/branch/develop/graph/badge.svg)](https://codecov.io/gh/panoptes/POCS)
[![astropy](http://img.shields.io/badge/powered%20by-AstroPy-orange.svg?style=flat)](http://www.astropy.org/)

<!-- <img src="http://www.projectpanoptes.org/images/units/PAN001_sunset_02.png" alt="PANOPTES unit PAN001 on Mauna Loa" style="border: 1px solid;" /> -->

# Overview

[PANOPTES](http://projectpanoptes.org) is an open source citizen science project that is designed to find exoplanets with digital cameras. The goal of PANOPTES is to establish a global network of of robotic cameras run by amateur astronomers and schools in order to monitor, as continuously as possible, a very large number of stars. For more general information about the project, including the science case and resources for interested individuals, see the [project overview](http://projectpanoptes.org/v1/overview/).

POCS (PANOPTES Observatory Control System) is the main software driver for the PANOPTES unit, responsible for high-level control of the unit. There are also files for a one-time upload to the arduino hardware, as well as various scripts to read information from the environmental sensors. 

# Getting Started

POCS is designed to control a fully constructed PANOPTES unit.  Additionally, POCS can be run with simulators when hardware is not present or when the system is being developed.

For information on building a PANOPTES unit, see the main [PANOPTES](http://projectpanoptes.org) website.

To get started with POCS there are three easy steps:

1. **Setup** POCS on the computer you will be using for your unit or for development.
2. **Test** your POCS setup by running our testing script
3. **Start using POCS!**

See below for more details.

## Setup

* [Computer setup](https://github.com/panoptes/POCS/wiki/Panoptes-Computer-Setup)

## Test POCS

If you have set up POCS, either for development or to run a unit, the next step is to test your setup. This is easy to do using our built-in test suite. In a terminal, simply type:

```bash
> cd $POCS
> pytest
```

This may take a few minutes as there are a lot of tests to run! If you experience any errors, ask for check the [Issues](https://github.com/panoptes/POCS/issues) listed above or ask one of our friendly team members!

## Use POCS

### For running a unit

Before running a unit there are a couple of things you should do to ensure the safety of your hardware.

* Go over the hardware setup checklist (coming soon!)
* Test your Home and Park positions (comming soon!)
* Do a [polar alignment test](https://github.com/panoptes/POCS/wiki/Polar-Alignment-Test)

### For helping develop POCS software

See [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES)

Links
-----

- PANOPTES Homepage: http://projectpanoptes.org
- Source Code: http://github.com/panoptes/POCS
