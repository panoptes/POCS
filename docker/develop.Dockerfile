ARG IMAGE_URL=gcr.io/panoptes-exp/panoptes-pocs:latest
FROM ${IMAGE_URL}

LABEL description="Installs the local folder in develop mode (i.e. pip install .e). \
Used for running the tests and as a base for the for developer-env image."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh

ENV PANUSER=panoptes
ENV PANDIR $pan_dir
ENV POCS $pocs_dir

# panoptes-utils
USER ${PANUSER}
COPY --chown=panoptes:panoptes . "${PANDIR}/POCS/"
RUN cd "${PANDIR}/POCS" && \
    pip install -e ".[testing,google]"

# Cleanup apt.
USER root
RUN apt-get autoremove --purge -y && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${POCS}

# Entrypoint runs gosu with panoptes user.
CMD ["/bin/zsh"]
