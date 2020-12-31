ARG image_url=gcr.io/panoptes-exp/panoptes-utils:develop
FROM ${image_url} AS pocs-base

LABEL description="Installs the panoptes-pocs module from GitHub. \
Used as a production image, i.e. for running on PANOPTES units."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"
ARG pip_extras="[testing,google]"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ENV PANDIR $pan_dir
ENV POCS $pocs_dir

# Install system dependencies.
USER root
RUN apt-get update && apt-get install --no-install-recommends --yes \
        gphoto2 \
        less \
        udev

# Install the module.
WORKDIR "${POCS}"
COPY . .
RUN echo "Installing editable module with ${pip_extras}" && \
    "${PANDIR}/conda/bin/pip" install -e ".${pip_extras}" && \
    # Cleanup
    apt-get autoremove --purge --yes && \
    apt-get autoclean --yes && \
    apt-get --yes clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Cleanup conda.
    "${PANDIR}/conda/bin/conda" clean -tipy
