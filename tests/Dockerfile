ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash
ENV PYTHONUNBUFFERED 1

ENV POCS "/panoptes-pocs"

ARG userid=1000
ARG pip_extras="[focuser,google,testing]"
ARG index_url="http://data.astrometry.net/4100/index-4111.fits"

USER "${userid}"

# Set up some common directories
WORKDIR /tmp
RUN echo "Building from ${image_url}:${image_tag}" && \
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
RUN mamba env update -n base -f environment.yaml && \
    mamba clean -tipy --force-pkgs-dirs

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .

RUN echo "Installing ${pip_install_name} module with ${pip_install_extras}" && \
    pip install --no-cache-dir -e ".${pip_extras}" && \
    # Cleanup
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "pytest" ]
