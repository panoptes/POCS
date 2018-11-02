# PANOPTES development container
# Build with:
#
#         docker build --tag panoptes/build --file $POCS/ci/Dockerfile-3 -- $POCS
#
# This makes $POCS the "context" for the build, i.e. the root folder
# from where files such as requirements.txt may be copied.

FROM ubuntu:bionic as build-env

LABEL description="PANOPTES Development Container"
LABEL author="Developers for PANOPTES project"
LABEL url="https://github.com/panoptes/POCS"

ARG pan_dir=/var/panoptes

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV ENV /root/.bashrc
ENV SHELL /bin/bash
ENV PANDIR $pan_dir
ENV PANLOG $PANDIR/logs 
ENV POCS $PANDIR/POCS  
ENV PAWS $PANDIR/PAWS  
ENV PANUSER root
ENV SOLVE_FIELD=/usr/bin/solve-field

################################################################################
# Several update steps before our custom commands. By rarely changing these
# commands, we allow the caching that 'docker build' performs to save us some
# time when iterating on the Panoptes specific steps (i.e. instead of executing
# these, the cached image layer is used).

RUN \
    # Suppress prompting for input during package processing.
    export DEBIAN_FRONTEND=noninteractive && \

    # Update the information we know about package versions.
    apt-get update --fix-missing && \

    # apt-utils is used later when we install some other packages, so
    # streamline those installs by installing it early.
    apt-get install --yes apt-utils && \

    # Install the tzdata package now with interactive prompting disabled.
    # Conveniently, the default timezone is UTC.
    apt-get install --yes tzdata && \

    # Upgrade other packages.
    apt-get upgrade --yes

################################################################################
# DO NOT KEEP THIS LONG TERM!
# Just using during editing and testing of install-dependencies.sh.

WORKDIR $POCS/scripts
COPY scripts/install install
RUN install/install-apt-packages.sh install/apt-packages-list.for-ci.txt
WORKDIR $POCS
RUN rm -rf scripts

################################################################################

# Make sure we have the appropriate bash version.
RUN rm /bin/sh \
 && ln -s /bin/bash /bin/sh

WORKDIR $POCS

# Copy POCS sources (not git repository) into this temporary directory.
#
# TODO(jamessynge): Use a command like the following to generate a list
# of files/directories in POCS to copy, and a script that inserts that
# into here for copying.
#
#         git ls-tree HEAD | cut -d$'\t' -f2 | xargs -i echo "COPY {} {}"
# 
# This command produces a single line version, which I've hand wrapped below.
#
#         echo COPY $(git ls-tree HEAD | cut -d$'\t' -f2) '$POCS/'

# First we copy the files and directories least likely to change while
# iterating on the building of the Docker image.
COPY .codecov.yml .coveragerc .gitignore .gitmodules .pycodestyle.cfg \
     .readthedocs.yml .style.yapf .travis.yml CODE_OF_CONDUCT.md \
     CONTRIBUTING.md Changelog.md LICENSE.txt README.md conftest.py \
     matplotlibrc setup.cfg setup.py \
  ./

COPY bin bin
COPY conf_files conf_files
COPY docs docs
COPY examples examples
COPY peas peas
COPY pocs pocs
COPY resources resources

# Next we copy those files and directories that we tend to change while developing
# or updating the docker image (as opposed to POCS).
COPY requirements.txt .
COPY ci ci
COPY scripts scripts

# Create the directories that the installer expects to be there.
RUN $POCS/scripts/install/create-core-panoptes-directories.sh

# Now the biggest step, installing the dependencies.
RUN DEBIAN_FRONTEND=noninteractive \
    $POCS/scripts/install/install-dependencies.sh \
        --no-mongodb --no-astrometry-indices
