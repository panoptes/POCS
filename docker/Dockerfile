ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS panoptes-pocs-base

ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest"

LABEL description="PANOPTES Observatory Control System (POCS) Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1

ARG userid=1000
ENV USERID $USERID

ARG app_dir=/panoptes-pocs
ENV APP_DIR $app_dir

ARG image_dir=/images
ARG log_dir=/logs

WORKDIR "${APP_DIR}"
USER "${USERID}"

# Dependencies and directories.
RUN echo "Building from ${image_url}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get install -y --no-install-recommends \
        inotify-tools astrometry-data-tycho2-10-19 && \
    # Set up directories in PANUSER home.
    sudo mkdir "$image_dir" && sudo chown -R "${USERID}:${USERID}" "$image_dir" && \
    sudo mkdir "$log_dir" && sudo chown -R "${USERID}:${USERID}" "$log_dir" && \
    sudo chown -R "${USERID}:${USERID}" "${APP_DIR}"

# Set up arduino cli tools.
RUN echo "Installing arduino-cli from ${arduino_url}" && \
    wget "${arduino_url}_Linux_$(uname -m | sed 's/x86_64/64bit/' | sed 's/aarch64/ARM64/').tar.gz" \
        -O arduino-cli.tar.gz && \
    tar zxvf arduino-cli.tar.gz && \
    mkdir -p "${HOME}/.local/bin" && \
    mv arduino-cli "${HOME}/.local/bin/arduino-cli"  && \
    rm LICENSE.txt && rm arduino-cli.tar.gz

FROM panoptes-pocs-base AS panoptes-pocs-dependencies

# Update conda environment with dependencies.
COPY docker/environment.yaml .
RUN echo "Updating conda environment" && \
    mamba env update -n base -f environment.yaml && \
    mamba clean -tipy --force-pkgs-dirs

FROM panoptes-pocs-dependencies AS panoptes-pocs

ARG pip_install_name="."
ARG pip_install_extras="[google]"

COPY --chown="${USERID}:${USERID}" . .
RUN echo "Installing ${pip_install_name} module with ${pip_install_extras}" && \
    pip install --no-cache-dir "${pip_install_name}${pip_install_extras}" && \
    # Cleanup
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

# TODO replace with pocs-cli.
CMD [ "ipython -i scripts/pocs-ipython-startup.py" ]
