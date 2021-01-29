ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash

ENV POCS "/POCS"

ARG userid=1000
ARG pip_extras="[focuser,google,testing]"

USER "${userid}"

# Set up some common directories
WORKDIR /tmp
RUN echo "Building from ${image_name}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get -y full-upgrade && \
    sudo apt-get install -y --no-install-recommends \
        gphoto2 \
        astrometry-data-tycho2 && \
    sudo mkdir /images && sudo chown -R "${userid}:${userid}" /images && \
    sudo mkdir /logs && sudo chown -R "${userid}:${userid}" /logs && \
    sudo mkdir "${POCS}" && sudo chown -R "${userid}:${userid}" "${POCS}"

COPY docker/environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .
RUN /conda/bin/pip install -e ".${pip_extras}" && \
    # Cleanup
    /conda/bin/pip cache purge && \
    /conda/bin/conda clean -tipy && \
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config git && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "pytest" ]
