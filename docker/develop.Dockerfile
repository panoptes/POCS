ARG IMAGE_URL=gcr.io/panoptes-exp/panoptes-utils:latest
FROM ${IMAGE_URL} AS pocs-base

LABEL description="Installs the panoptes-pocs module in local editable \
mode. This requires the entire git history to be present. Used for testing."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG pandir=/var/panoptes
ARG arduino_url="https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh"
ARG gphoto2_url="https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh
ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS
ENV SOLVE_FIELD /usr/bin/solve-field

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc libncurses5-dev udev \
    # GPhoto2
    && wget $gphoto2_url \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    && rm gphoto2-updater.sh \
    # arduino-cli
    && curl -fsSL $arduino_url | BINDIR="/usr/local/bin" sh

# panoptes-utils
USER ${PANUSER}
COPY --chown=panoptes:panoptes . "${PANDIR}/POCS/"
RUN cd "${PANDIR}/POCS" && \
    pip3 install -U -e ".[testing,google]"

# Cleanup apt.
USER root
RUN apt-get autoremove --purge -y \
        autoconf \
        automake \
        autopoint \
        build-essential \
        gcc \
        gettext \
        libtool \
        pkg-config && \
    apt-get autoremove --purge -y && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${POCS}
CMD ["/bin/zsh"]
