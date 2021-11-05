ARG image_url=gcr.io/panoptes-exp/panoptes-pocs
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash
ENV PYTHONUNBUFFERED 1

ENV POCS "/panoptes-pocs"

ARG userid=1000
ARG pip_extras="[focuser,google,testing]"

USER "${userid}"

# Set up some common directories
WORKDIR /tmp
RUN echo "Building from ${image_url}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get -y full-upgrade && \
    sudo apt-get install -y --no-install-recommends gphoto2

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .

RUN echo "Installing module with ${pip_extras}" && \
    pip install -e ".${pip_extras}" && \
    # Cleanup
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

CMD [ "pytest" ]
