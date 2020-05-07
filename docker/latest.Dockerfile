ARG arch=amd64

FROM gcr.io/panoptes-exp/panoptes-utils:latest AS pocs-base
LABEL maintainer="developers@projectpanoptes.org"

ARG pandir=/var/panoptes
ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_64bit.tar.gz"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh
ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS
ENV USER panoptes

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        gcc libncurses5-dev udev \
    # GPhoto2
    && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    && rm gphoto2-updater.sh \
    # arduino-cli
    && wget -q $arduino_url -O arduino-cli.tar.gz \
    # Untar and capture output name (NOTE: assumes only one file).
    && tar xvfz arduino-cli.tar.gz \
    && mv arduino-cli /usr/local/bin/arduino-cli \
    && chmod +x /usr/local/bin/arduino-cli

USER $PANUSER

# Copy just requirements and install.
COPY --chown=panoptes:panoptes ./requirements.txt ${POCS}/
RUN cd ${POCS} && \
    # First deal with pip and PyYAML - see https://github.com/pypa/pip/issues/5247
    pip install --no-cache-dir --no-deps --ignore-installed pip PyYAML && \
    # Install requirements
    pip install --no-cache-dir -r requirements.txt

# Copy over entire directory now and install in editable mode.
COPY --chown=panoptes:panoptes . ${POCS}
RUN pip install --no-cache-dir -e .

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
