ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash

ENV POCS "/panoptes-pocs"

ARG userid=1000
ARG pip_extras="[focuser,google,testing]"
ARG index_url="http://data.astrometry.net/4100/index-4111.fits"

USER "${userid}"

# Set up some common directories
WORKDIR /tmp
RUN echo "Building from ${image_name}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get -y full-upgrade && \
    sudo apt-get install -y --no-install-recommends \
        gphoto2 && \
    # Index file used for tests.
    sudo wget "${index_url}" -O /usr/share/astrometry/index-4111.fits && \
    # Support directories.
    sudo mkdir /images && sudo chown -R "${userid}:${userid}" /images && \
    sudo mkdir /logs && sudo chown -R "${userid}:${userid}" /logs && \
    sudo mkdir "${POCS}" && sudo chown -R "${userid}:${userid}" "${POCS}"

COPY docker/environment.yaml .
RUN conda env update -n base -f environment.yaml

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .
RUN pip install -e ".${pip_extras}" && \
    # panoptes-utils from dev.
    pip install --no-cache-dir "git+https://github.com/panoptes/panoptes-utils@develop#egg=panoptes-utils[config]" && \
    # Cleanup
    pip cache purge && \
    conda clean -tipy && \
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config git && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "pytest" ]
