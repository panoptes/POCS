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

COPY docker/environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml

# Set up some common directories
RUN echo "Building from ${image_name}:${image_tag}" && \
    sudo mkdir /images && sudo chown -R "${userid}:${userid}" /images && \
    sudo mkdir /logs && sudo chown -R "${userid}:${userid}" /logs && \
    sudo mkdir "${POCS}" && sudo chown -R "${userid}:${userid}" "${POCS}"

ARG pip_install_extras="[google]"

WORKDIR "${POCS}"
RUN echo "Installing panoptes-pocs module with ${pip_install_extras}" && \
    /conda/bin/pip install -e "panoptes-pocs${pip_install_extras}" && \
    # Cleanup
    /conda/bin/pip cache purge && \
    /conda/bin/conda clean -tipy && \
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config git && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]

# TODO Change to pocs cli.
CMD [ "/bin/bash" ]
