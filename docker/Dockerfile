ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest"

LABEL description="PANOPTES Observatory Control System Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ARG userid=1000
ENV USERID $userid

ARG app_dir=/panoptes-pocs
ENV APP_DIR $app_dir

ARG images_dir=/images
ARG log_dir_dir=/logs

WORKDIR /
USER "${userid}"

# Dependencies and directories.
RUN echo "Building from ${image_name}:${image_tag}" && \
    sudo apt-get update && \
    sudo apt-get install -y --no-install-recommends \
        gphoto2 \
        astrometry-data-tycho2-10-19 && \
    # Set up directories in PANUSER home.
    sudo mkdir $image_dir && sudo chown -R "${userid}:${userid}" $image_dir && \
    sudo mkdir $log_dir && sudo chown -R "${userid}:${userid}" $log_dir && \
    sudo mkdir "${APP_DIR}" && sudo chown -R "${userid}:${userid}" "${APP_DIR}"

# Set up arduino cli tools.
RUN echo "Installing arduino-cli from ${arduino_url}" && \
    wget "${arduino_url}_Linux_$(uname -m | sed 's/x86_64/64bit/' | sed 's/aarch64/ARM64/').tar.gz" \
        -O arduino-cli.tar.gz && \
    tar zxvf arduino-cli.tar.gz && \
    mkdir -p "${HOME}/bin" && \
    mkdir -p "${HOME}/.local/bin" && \
    mv arduino-cli "${HOME}/.local/bin/arduino-cli"  && \
    rm LICENSE.txt && rm arduino-cli.tar.gz

WORKDIR "${APP_DIR}"

# Update conda environment with dependencies.
COPY docker/environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml

ARG pip_install_name="."
ARG pip_install_extras="[google]"

COPY --chown="${userid}:${userid}" . .
RUN echo "Installing ${pip_install_name} module with ${pip_install_extras}" && \
    /conda/bin/pip install "${pip_install_name}${pip_install_extras}" && \
    # Cleanup
    /conda/bin/pip cache purge && \
    /conda/bin/conda clean -tipsy && \
    sudo apt-get autoremove --purge --yes \
        gcc pkg-config git && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

# TODO replace with pocs-cli.
CMD [ "ipython" ]
