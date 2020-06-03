ARG IMAGE_URL=gcr.io/panoptes-exp/panoptes-utils:latest
FROM ${IMAGE_URL} AS pocs-base

LABEL description="Installs the panoptes-pocs module from pip. \
Used as a production image, i.e. for running on PANOPTES units."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG pandir=/var/panoptes
ARG arduino_url="https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh"
ARG gphoto2_url="https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh
ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS
ENV USER panoptes
ENV PANUSER panoptes

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc libncurses5-dev udev \
    # GPhoto2
    && wget $gphoto2_url \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    && rm gphoto2-updater.sh \
    # arduino-cli
    && curl -fsSL $arduino_url | BINDIR="/usr/local/bin" sh \
    # Install the module.
    && pip install "panoptes-pocs[google]" \
    # Make sure $PANUSER owns $PANDIR.
    && chown -R "${PANUSER}:${PANUSER}" "${PANDIR}"

# Cleanup apt.
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
