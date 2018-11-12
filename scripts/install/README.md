# PANOPTES Software Installation Tools

## Installation Procedure

__MUCH WORK IS NEEDED HERE__

### Initial Setup of Bare Computer

#### Install Ubuntu 18.04 Desktop
#### Create Primary Account

When prompted to create the primary account during the install of Ubuntu,
create an account with your name (e.g. james)...

### Install Linux Packages (Software) Needed to Install PANOPTES

```
sudo apt-get update
sudo apt-get install --yes git
```

### Install Linux Packages (Software) Needed by PANOPTES

*This is where we need a single script that we can fetch from github
rather than use git clone.*

#### Create Secondary (PANOPTES) Account

Create an account for user `panoptes` with all the privileges of the
primary user, especially plugdev (needed for access to serial ports).

> If using docker, then also add the user to the docker group.
> If you don't know what that means, then skip adding to the docker group.

## Script Descriptions

### default-env-vars.sh

Sets the PANOPTES related environment variables to their default values.
Once you've run install-dependencies.sh you won't need this script anymore.

### run-apt-cacher-ng-in-docker.sh

This is a tool primarily for developers and testers of the PANOPTES
software. It helps speed up the install-apt-packages.sh in the case
that you need to run that command many times, as when testing changes
to the install scripts. In particular, it starts a docker container
running a caching proxy that listens on port 3142 for requests for
apt packages. If it hasn't seen a request for that package before,
it pass the request on to the "real" package repository, stores the
fetched package in a directory and returns the package to the caller
(e.g. to `apt-get`).

Requires that `docker` be installed. Learn more on the
(docker site)[https://docs.docker.com/install/linux/docker-ce/ubuntu/].

### configure-apt-cache.sh

If you've run run-apt-cacher-ng-in-docker.sh, then you can either
tell apt-get where to find the caching proxy each time or you can
run this script which permanently records the fact that you have
a caching proxy running on port 3142.

```
   $ $POCS/scripts/install/configure-apt-cache.sh 3142
```

### install-apt-packages.sh

Installs the required Linux open source software onto the machines.
The user that executes this must be a member of the sudo group
(i.e. allowed to run commands as `root`).
If you're running the caching proxy (see above), and have NOT
run configure-apt-cache.sh, then you'll want to tell this script
where to find the proxy:

```
   $ APT_PROXY_PORT=3142 $POCS/scripts/install/install-apt-packages.sh
```

### install-dependencies.sh

Installs the open source software that the PANOPTES software depends upon,
including running install-apt-packages.sh.
Writes a script ($PANDIR/set-panoptes-env.sh) that sets up your shell with
the correct environment variables for running the PANOPTES software, and
adds a call to that script into your shell's initialization script.

### install-helper-functions.sh

This isn't intended to be executed directly; instead it provides a bunch of
functions that are used by several of the scripts described above.

## Resource (List) Descriptions

These files list packages to be installed, and are read by the scripts
described above.

### apt-packages-list.txt

List of Linux packages to be installed; these are "native" packages (i.e.
compiled software). Installing such packages requires `root` privileges
in order to execute `apt-get install` (used by `install-apt-packages.sh`
and `install-dependencies.sh`).

### conda-packages-list.txt

List of packages in the Anaconda format, many of which are implemented in
Python, but not all. These do not require `root` privileges to install.

### $POCS/requirements.txt

List of packages in the Wheel format, installed using the `pip` tool.
These do not require `root` privileges to install.
