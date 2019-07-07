ARG arch=amd64

FROM gcr.io/panoptes-survey/panoptes-utils:$arch AS pocs-base
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ARG user=root
ARG pandir=/var/panoptes

ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli-latest-linux64.tar.bz2"

ENV USER $user
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash
ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS
ENV PANUSER $user

COPY . ${POCS}

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        byobu \
        ffmpeg \
        libncurses5-dev \
        udev \
        vim-nox \
    # GPhoto2
    && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    # arduino-cli
    && wget -q $arduino_url -O arduino-cli.tar.bz2 \
    # Untar and capture output name (NOTE: assumes only one file).
    && ARDUINO_FILE=$(tar xvfj arduino-cli.tar.bz2) \
    && mv "${ARDUINO_FILE}" /usr/local/bin/arduino-cli \
    && chmod +x /usr/local/bin/arduino-cli \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm gphoto2-updater.sh

FROM pocs-base

# POCS
RUN cd ${POCS} \
    # First deal with pip and PyYAML - see https://github.com/pypa/pip/issues/5247
    && "/home/${USER}/envs/${CONDA_ENV}/bin/pip" install --no-cache-dir --no-deps --ignore-installed pip PyYAML \
    && "/home/${USER}/envs/${CONDA_ENV}/bin/pip" install --no-cache-dir -Ur requirements.txt \
    && "/home/${USER}/envs/${CONDA_ENV}/bin/pip" install --no-cache-dir -e . \
    # Link conf_files to $PANDIR
    && ln -s ${POCS}/conf_files/ ${PANDIR}/

WORKDIR ${POCS}

USER ${user}

CMD ["/bin/zsh"]

