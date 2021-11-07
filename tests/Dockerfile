ARG image_url=gcr.io/panoptes-exp/panoptes-pocs
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash
ENV PYTHONUNBUFFERED 1

ENV POCS "/panoptes-pocs"
ARG app_dir=/panoptes-pocs
ENV APP_DIR $app_dir

ARG userid=1000
ARG pip_extras="[google,testing]"

WORKDIR "${APP_DIR}"
USER "${userid}"

# Set up some common directories.
RUN sudo apt-get update && \
    sudo apt-get install -y --no-install-recommends gphoto2 && \
    # Cleanup
    sudo apt-get autoremove --purge --yes gcc pkg-config && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

CMD [ "pytest" ]
