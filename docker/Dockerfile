ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

LABEL description="PANOPTES Observatory Control System Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV POCS "/POCS"

ARG userid=1000
ENV USERID $userid

USER "${userid}"

# Set up some common directories
RUN echo "Building from ${image_name}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get install -y --no-install-recommends \
        gphoto2 \
        astrometry-data-tycho2-10-19 && \
    sudo mkdir /images && sudo chown -R "${userid}:${userid}" /images && \
    sudo mkdir /logs && sudo chown -R "${userid}:${userid}" /logs && \
    sudo mkdir "${POCS}" && sudo chown -R "${userid}:${userid}" "${POCS}"

COPY docker/environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml

ARG pip_install_name="."
ARG pip_install_extras="[google]"

COPY --chown="${userid}:${userid}" . .
RUN echo "Installing ${pip_install_name} module with ${pip_install_extras}" && \
    /conda/bin/pip install "${pip_install_name}${pip_install_extras}" && \
    # Cleanup
    /conda/bin/pip cache purge && \
    /conda/bin/conda clean -fay && \
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config git && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" docker/docker-compose.yaml .
COPY --chown="${userid}:${userid}" conf_files conf_files
COPY --chown="${userid}:${userid}" resources resources
COPY --chown="${userid}:${userid}" scripts scripts
COPY --chown="${userid}:${userid}" tests/data tests/data

ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "ipython" ]
