ARG arch=amd64

FROM gcr.io/panoptes-survey/panoptes-utils:$arch AS pocs-base
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ARG pandir=/var/panoptes

ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli-latest-linux64.tar.bz2"

ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS

COPY . ${POCS}

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        byobu \
        ffmpeg \
        gcc \
        pkg-config \
        libncurses5-dev \
        udev \
        vim-nox \
    # GPhoto2
    && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    # arduino-cli
    && wget -q $arduino_url -O arduino-cli.tar.bz2 \
    && bunzip2 arduino-cli.tar.bz2 \
    && tar xof arduino-cli.tar \
    && rm arduino-cli.tar \
    # Don't know exact name of untarred file.
    && ARDUINO_FILE="$(ls arduino-cli*)" \
    # Rename so we do know.
    && mv ${ARDUINO_FILE} arduino-cli \
    && chmod +x arduino-cli \
    && mv arduino-cli /usr/local/bin/ \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm gphoto2-updater.sh


FROM pocs-base

ARG which_pip=pip

# POCS
RUN cd ${POCS} \
    && $which_pip install --no-cache-dir --no-deps -r requirements.txt \
    && $which_pip install --no-cache-dir --no-deps -e . \
    # Link conf_files to $PANDIR
    && ln -s ${POCS}/conf_files/ ${PANDIR}/

WORKDIR ${POCS}

CMD ["/bin/zsh"]

