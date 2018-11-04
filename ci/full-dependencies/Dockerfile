# PANOPTES Test Dependencies Container
# Build with:
#
#         $POCS/ci/full-dependencies/docker-build.sh

FROM debian:stable-slim as build-env

LABEL description="PANOPTES Test Dependencies Container"
LABEL author="Developers for PANOPTES project"
LABEL url="https://github.com/panoptes/POCS"

ARG apt_proxy_port=
ARG pan_dir=/var/panoptes

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV ENV /root/.bashrc
ENV SHELL /bin/bash
ENV PANDIR $pan_dir
ENV PANLOG $PANDIR/logs
ENV POCS $PANDIR/POCS
ENV PAWS $PANDIR/PAWS
ENV PANUSER root
ENV SOLVE_FIELD /usr/bin/solve-field
ENV APT_PROXY_PORT $apt_proxy_port

# Testing script, should you need it.
# COPY run_phase_0_test.sh .
# RUN ./run_phase_0_test.sh && rm run_phase_0_test.sh && exit 1

# Set the WORKDIR to a directory we can blow away at the end.
WORKDIR /workdir

################################################################################
# Install well established, relatively stable dependencies first so that docker
# build caching will create a layer with these items.

COPY run_phase_1_apt_core.sh .
RUN ./run_phase_1_apt_core.sh && rm run_phase_1_apt_core.sh

################################################################################
# Now install dependencies that are more likely to change (both the actual list
# of packages, their versions and installation flags).

COPY run_phase_2_apt_extras.sh .
RUN ./run_phase_2_apt_extras.sh && rm run_phase_2_apt_extras.sh

################################################################################
# Copy in all the files from the context, which should be small in total size.
COPY * ./

################################################################################
# Install miniconda and create the panoptes environment.

# First just get miniconda and the panoptes environment created.
RUN DO_INSTALL_CONDA_PACKAGES=0 DO_PIP_REQUIREMENTS=0 \
    ./install-miniconda.sh

# Then install conda packages, but not pip packages.
RUN DO_INSTALL_CONDA_PACKAGES=1 DO_PIP_REQUIREMENTS=0 \
    REQUIREMENTS_PATH=./requirements.txt \
    ./install-miniconda.sh

# Now install the pip packages.
RUN DO_INSTALL_CONDA_PACKAGES=0 DO_PIP_REQUIREMENTS=1 \
    REQUIREMENTS_PATH=./requirements.txt \
    ./install-miniconda.sh

################################################################################
# Create the directories that the installer expects to be there.
RUN ./create-core-panoptes-directories.sh

# This just sets up the environment variables and shell profiles for the user.
RUN ./install-dependencies.sh \
        --no-apt-get --no-mongodb --no-conda --no-conda-packages \
        --no-astrometry --no-astrometry-indices --no-pip-requirements

CMD ["/bin/bash"]