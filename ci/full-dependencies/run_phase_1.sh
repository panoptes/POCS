#!/bin/bash -ex

# Suppress prompting for input during package processing.
export DEBIAN_FRONTEND=noninteractive

# Update the information we know about package versions.
apt-get update --fix-missing

# apt-utils is used later when we install some other packages, so
# reduce the number of error messages from debconf by installing
# this early.
apt-get install --no-install-recommends --yes apt-utils

# Install the tzdata package now with interactive prompting disabled.
# Conveniently, the default timezone is UTC.
apt-get install --no-install-recommends --yes tzdata

# Docker best practices calls for cleaning the apt cache before
# the end of this RUN so that it is not stored in the image.
rm -rf /var/lib/apt/lists/*