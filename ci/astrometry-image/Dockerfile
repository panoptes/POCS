# Astrometry Image
# Build with:
#
#    export ASTROMETRY_VERSION=0.76
#    export TAG=panoptes/astrometry-${ASTROMETRY_VERSION}
#    docker build \
#        --tag "${TAG}" \
#        --build-arg "astrometry_version=${ASTROMETRY_VERSION}" \
#        --file $POCS/ci/astrometry-image/Dockerfile -- $POCS
#
# This makes $POCS the "context" for the build, i.e. the root folder
# from where files such as requirements.txt may be copied.

FROM debian:latest

LABEL description="Astrometry Image"
LABEL author="Developers for PANOPTES project"
LABEL url="https://github.com/panoptes/POCS"
LABEL dockerfile="https://github.com/panoptes/POCS/blob/develop/ci/astrometry-image/Dockerfile"

ARG astrometry_version=0.76

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV ENV /root/.bashrc
ENV SHELL /bin/bash

################################################################################
# Several update steps before our custom commands. By rarely changing these
# commands, we allow the caching that 'docker build' performs to save us some
# time when iterating on the Panoptes specific steps (i.e. instead of executing
# these, the cached image layer is used).

COPY scripts/install/prepare-apt.sh /tmp/prepare-apt.sh

RUN echo $PATH
RUN which bash
RUN /tmp/prepare-apt.sh

################################################################################
# Install the dependencies needed for downloading and building astrometry.
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libcairo2-dev libnetpbm10-dev netpbm libpng-dev libjpeg-dev \
        python-numpy python-pyfits python-dev zlib1g-dev libbz2-dev swig \
        libcfitsio-dev 

        libbz2-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip python-dev
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip python-dev \
        python-numpy
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip python-dev \
        python-numpy python-pyfits
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip python-dev \
        python-numpy python-pyfits swig
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get install --yes \
        libbz2-dev libcfitsio-dev libjpeg-dev libnetpbm10-dev libpng-dev \
        netpbm zlib1g-dev libcairo2-dev wget make gcc unzip python-dev \
        python-numpy python-pyfits swig libbz2

################################################################################
# Fetch and build astrometry in /astrometry.net-${astrometry_version}, then
# install into /astrometry.

COPY scripts/install/install-astrometry.sh /tmp/install-astrometry.sh
RUN PANDIR= ASTROMETRY_VERSION="${astrometry_version}" LDFLAGS=-static \
    /tmp/install-astrometry.sh
