ARG arch=amd64

FROM gcr.io/panoptes-survey/panoptes-utils:$arch AS pocs-base
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ARG pandir=/var/panoptes
ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli-latest-linux64.tar.bz2"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh
ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS

COPY . ${POCS}

RUN apt-get update \
    && apt-get install --no-install-recommends --yes gcc libncurses5-dev udev \
    # GPhoto2
    && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    && rm gphoto2-updater.sh \
    # arduino-cli
    && wget -q $arduino_url -O arduino-cli.tar.bz2 \
    # Untar and capture output name (NOTE: assumes only one file).
    && ARDUINO_FILE=$(tar xvfj arduino-cli.tar.bz2) \
    && mv "${ARDUINO_FILE}" /usr/local/bin/arduino-cli \
    && chmod +x /usr/local/bin/arduino-cli \
    # POCS
    && cd ${POCS} \
    # First deal with pip and PyYAML - see https://github.com/pypa/pip/issues/5247
    && pip install --no-cache-dir --no-deps --ignore-installed pip PyYAML \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e . \
    # Link conf_files to $PANDIR
    && ln -s ${POCS}/conf_files/ ${PANDIR}/ \
    # Cleanup
    && apt-get autoremove --purge -y \
        autoconf \
        automake \
        autopoint \
        build-essential \
        gcc \
        gettext \
        libltdl-dev \
        libpopt-dev \
        libtool \
        libudev-dev \
        libusb-dev \
        pkg-config \
    && apt-get autoremove --purge -y \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${POCS}

CMD ["/bin/zsh"]
