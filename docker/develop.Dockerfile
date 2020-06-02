ARG BASE_IMAGE=gcr.io/panoptes-exp/panoptes-pocs:latest
FROM ${BASE_IMAGE}

LABEL description="Installs the local folder in develop mode (i.e. pip install .e). \
Used for running the tests and as a base for the for developer-env image."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG panuser=panoptes
ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh

ENV PANDIR $pan_dir
ENV PANUSER $panuser
ENV POCS $pocs_dir
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc git pkg-config

USER $PANUSER
# Can't seem to get around the hard-coding for chown.
COPY --chown=panoptes:panoptes . ${POCS}/
RUN cd ${PANDIR}/POCS && \
    pip install -e ".[google,testing]"

# Cleanup apt.
USER root
RUN apt-get autoremove --purge -y && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${POCS}

# Entrypoint runs gosu with panoptes user.
CMD ["/bin/zsh"]
