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

[PANOPTES](http://projectpanoptes.org) is an open source citizen science project 
that is designed to find exoplanets with digital cameras. The goal of PANOPTES is 
to establish a global network of of robotic cameras run by amateur astronomers 
and schools in order to monitor, as continuously as possible, a very large number 
of stars. For more general information about the project, including the science 
case and resources for interested individuals, see the 
[project overview](http://projectpanoptes.org/v1/overview/).

POCS (PANOPTES Observatory Control System) is the main software driver for the 
PANOPTES unit, responsible for high-level control of the unit. There are also 
files for a one-time upload to the arduino hardware, as well as various scripts 
to read information from the environmental sensors. 

# Getting Started

POCS is designed to control a fully constructed PANOPTES unit.  Additionally, 
POCS can be run with simulators when hardware is not present or when the system 
is being developed.

For information on building a PANOPTES unit, see the main [PANOPTES](http://projectpanoptes.org) website.

To get started with POCS there are three easy steps:

1. **Setup** POCS on the computer you will be using for your unit or for development.
2. **Test** your POCS setup by running our testing script
3. **Start using POCS!**

See below for more details.

## Setup

### Manual install

* [Computer setup](https://github.com/panoptes/POCS/wiki/Panoptes-Computer-Setup)
* While logged in as user panoptes:
   * Create /var/panoptes, owned by user panoptes (for a computer that will be
     controlling a PANOPTES unit), or as yourself for development of the
     PANOPTES software:
     ```bash
     sudo mkdir -p /var/panoptes
     sudo chown panoptes /var/panoptes
     chmod 755 /var/panoptes
     mkdir /var/panoptes/logs
     ```
   * Define these environment variables, both in your current shell and in
     `$HOME/.bash_profile` (to only apply to user panoptes) or in `/etc/profile`
     (to apply to all users).
     ```bash
     export PANDIR=/var/panoptes   # Main Dir
     export PANLOG=${PANDIR}/logs  # Log files
     export POCS=${PANDIR}/POCS    # Observatory Control
     export PAWS=${PANDIR}/PAWS    # Web Interface
     export PIAA=${PANDIR}/PIAA    # Image Analysis
     export PANUSER=panoptes       # PANOPTES linux user
     ```
   * Clone the PANOPTES software repositories into /var/panoptes:
     ```bash
     cd ${PANDIR}
     git clone https://github.com/panoptes/POCS.git
     git clone https://github.com/panoptes/PAWS.git
     git clone https://github.com/panoptes/PIAA.git
     ```
   * Install the software dependencies of the PANOPTES software:
     ```bash
     ${POCS}/scripts/install/install-dependencies.sh
     ```
   * To pickup the changes to PATH, etc., log out and log back in.
   * Run setup.py to install the software.
      * If you'll be doing development of the software, use these commands:
        ```bash
        python ${POCS}/setup.py develop
        python ${PIAA}/setup.py develop
        ```
      * If the computer is for controlling a PANOPTES unit, use these commands:
        ```bash
        python ${POCS}/setup.py install
        python ${PIAA}/setup.py install
        ```

### Docker

[Docker](https://www.docker.com/what-docker) is an application that lets you run existing
services, in this case POCS, on a kind of virtual machine. By running via Docker you
are guranteeing you are using a setup that works, saving you time on setup and 
other issues that you might run into doing a manual install.

Of course, this also means that you need to set up Docker. Additionally, you will
need to be able to log into our Google Docker container storage area so you can pull
down the existing image. The steps below should help you to get going.

#### Install Docker

Depending on what operating system you are using there are different ways of getting
Docker on your system. The Docker [installation page](https://www.docker.com/community-edition) 
should have all the answers you need.

#### Install gcloud

`gcloud` is a command line utility that lets you interact with many of the Google
cloud services. We will primarily use this to authenticate your account but this
is also used, for example, to upload images your PANOPTES unit takes.

See the gcloud [installation page](https://cloud.google.com/sdk/docs/#install_the_latest_cloud_tools_version_cloudsdk_current_version)
for easy install instructions.

#### Let Docker use gcloud

Docker needs to be able to use your `gcloud` login to pull the PANOPTES images. There
are some helper scripts to make this easier (from [here](https://cloud.google.com/container-registry/docs/advanced-authentication)):

```
gcloud components install docker-credential-gcr
docker-credential-gcr configure-docker
docker-credential-gcr gcr-login
```

#### Pull POCS container

```
 docker pull gcr.io/panoptes-survey/pocs:latest
```

#### Start the POCS image

```
docker run -it -p 9000:9000 --name pocs gcr.io/panoptes-survey/pocs
```

The POCS image will automatically start [Jupyter Lab](https://jupyter.org/) running
on port 9000 of your local browser. The above command should display a link that you
copy and paste into your browser to get you started.

## Test POCS

POCS comes with a testing suite that allows it to test that all of the software 
works and is installed correctly. Running the test suite by default will use simulators 
for all of the hardware and is meant to test that the software works correctly. 
Additionally, the testing suite can be run with various flags to test that attached 
hardware is working properly.

All of the test files live in `$POCS/pocs/tests`.

### Software Testing

There are a few scenarios where you want to run the test suite:

1. You are getting your unit ready and want to test software is installed correctly.
2. You are upgrading to a new release of software (POCS, its dependencies or the operating system).
2. You are helping develop code for POCS and want test your code doesn't break something.

#### Testing your installation

In order to test your installation you should have followed all of the steps above 
for getting your unit ready. To run the test suite, you will need to open a terminal 
and navigate to the `$POCS` directory.

```bash
# Change to $POCS directory
(panoptes-env) $ cd $POCS

# Run the software testing
(panoptes-env) $ pytest
```

> :bulb: NOTE: The test suite can take a while to run and often appears to be stalled. 
> Check the log files to ensure activity is happening. The tests can be cancelled by 
> pressing `Ctrl-c` (sometimes entering this command multiple times is required).

It is often helpful to view the log output in another terminal window while the test suite is running:

```bash
# Follow the log file
$ tail -f $PANDIR/logs/panoptes.log
```


The output from this will look something like:

```bash
(panoptes-env) $  pytest                                                                                                                                                     
=========================== test session starts ======================================
platform linux -- Python 3.5.2, pytest-3.2.3, py-1.4.34, pluggy-0.4.0                                                 
rootdir: /storage/panoptes/POCS, inifile:                       
plugins: cov-2.4.0                                                                                                     

collected 260 items                                                                                                                                                                                                                   
pocs/tests/test_base_scheduler.py ...............
pocs/tests/test_camera.py ........s..ssssss..................ssssssssssssssssssssssssss
pocs/tests/test_codestyle.py .
pocs/tests/test_config.py .............
pocs/tests/test_constraints.py ..............
pocs/tests/test_database.py ...
pocs/tests/test_dispatch_scheduler.py ........
pocs/tests/test_field.py ....
pocs/tests/test_focuser.py .......sssssss..
pocs/tests/test_images.py ..........
pocs/tests/test_ioptron.py .
pocs/tests/test_messaging.py ....
pocs/tests/test_mount_simulator.py ..............
pocs/tests/test_observation.py .................
pocs/tests/test_observatory.py ................s.......
pocs/tests/test_pocs.py ..........................
pocs/tests/test_utils.py .............
pocs/tests/bisque/test_dome.py ssss
pocs/tests/bisque/test_mount.py sssssssssss
pocs/tests/bisque/test_run.py s

=========================== 203 passed, 57 skipped, 6 warnings in 435.76 seconds ===================================

```

Here you can see that certain tests were skipped (`s`) for various reasons while 
the others passed. Skipped tests are skipped on purpose and thus are not considered 
failures. Usually tests are skipped because there is no attached hardware 
(see below for running tests with hardware attached). All passing tests are represented
by a single period (`.`) and any failures would show as a `F`. If there are any failures
while running the tests the output from those failures will be displayed.

#### Testing your code changes

> :bulb: NOTE: This step is meant for people helping with software development

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

**In Progress**

## Use POCS

### For running a unit

* [Polar alignment test](https://github.com/panoptes/POCS/wiki/Polar-Alignment-Test)

### For helping develop POCS software

See [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES)

Links
-----

- PANOPTES Homepage: http://projectpanoptes.org
- Source Code: http://github.com/panoptes/POCS
