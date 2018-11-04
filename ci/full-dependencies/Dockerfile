# PANOPTES development container
# Build with:
#
#         $POCS/ci/full-dependencies/docker-build.sh

FROM debian:stable-slim as build-env

LABEL description="PANOPTES Dependencies Container"
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
# Several apt steps before our custom commands. By rarely changing these
# commands, we allow the caching that 'docker build' performs to save us some
# time when iterating on the Panoptes specific steps (i.e. instead of executing
# these, the cached image layer is used).

COPY run_phase_*.sh /tmp/
RUN /tmp/run_phase_1.sh

################################################################################
# Now install dependencies related specifically to POCS.

RUN \
  #
  # Suppress prompting for input during package processing.
  #
  export DEBIAN_FRONTEND=noninteractive && \
  #
  # Update the information we know about package versions.
  #
  apt-get update --fix-missing && \
  #
  # Install packages we need...
  #
  apt-get install --no-install-recommends --yes \
    #
    # Astrometry and cfitsio.
    # Not sure if libcfitsio-dev is directly needed.
    #
    astrometry.net "astrometry-data-*" libcfitsio-bin libcfitsio-dev \
    #
    # Not sure if these are needed for testing POCS, or just for running.
    #
    dcraw gphoto2 exiftool \
    #
    # Cairo is a graphics library, and matplotlib can use it as a backend
    # for rendering.
    #
    libcairo2-dev \
    #
    # Graphviz is used for rendering the state machine of POCS.
    # Not sure if these are needed for testing POCS, or just for running.
    #
    graphviz libgraphviz-dev \
    #
    # Improves interaction with pocs_shell (via readline).
    #
    libncurses5-dev \
    #
    # Tools needed for installing miniconda.
    #
    wget \
    #
    # END OF LIST OF PACKAGES
    #
    && \
  #
  # Docker best practices calls for cleaning the apt cache before the end
  # of this RUN so that it is not stored in the image.
  #
  rm -rf /var/lib/apt/lists/*

################################################################################
# Install miniconda and create the panoptes environment.

WORKDIR $POCS/scripts
COPY scripts/install install
RUN install/install-miniconda.sh


RUN source scripts/install/install-functions.sh && \
    install_conda




RUN exit 1

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

# Now the biggest step, installing the dependencies, which here primarily means
# the Anaconda installation (i.e. for python related deps).
RUN DEBIAN_FRONTEND=noninteractive \
    $POCS/scripts/install/install-dependencies.sh \
        --no-apt-get --no-mongodb --no-astrometry-indices
