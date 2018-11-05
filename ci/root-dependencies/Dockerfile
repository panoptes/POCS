# PANOPTES Linux Package Dependencies Container
# Build with:
#
#         ./docker-build.sh

FROM debian:stable-slim as build-env

LABEL description="PANOPTES Linux Package Dependencies Container"
LABEL author="Developers for PANOPTES project"
LABEL url="https://github.com/panoptes/POCS"

ARG apt_proxy_port=
ARG pan_dir=/var/panoptes
ARG pan_user=root

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
#ENV ENV /root/.bashrc
#ENV SHELL /bin/bash
ENV SOLVE_FIELD /usr/bin/solve-field

# Testing script, should you need it.
# COPY run_phase_0_test.sh .
# RUN ./run_phase_0_test.sh && rm run_phase_0_test.sh && exit 1

################################################################################
# If there is an apt caching proxy running, tell apt where to find it. Note
# that this persists in an /etc/apt/... file, so isn't dependent on the ARG
# in the future, for good or ill.
COPY detect-apt-cache.sh .
RUN APT_PROXY_PORT=$apt_proxy_port ./detect-apt-cache.sh && \
    rm detect-apt-cache.sh

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

