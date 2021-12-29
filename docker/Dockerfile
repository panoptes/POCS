ARG image_url=python
ARG image_tag=3.10-slim-buster
FROM ${image_url}:${image_tag}

ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest"

LABEL description="PANOPTES Observatory Control System (POCS) Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1

ARG username=pocs-user
ARG userid=1000
ARG app_dir=/panoptes-pocs
ARG image_dir=/images
ARG log_dir=/logs
ARG pip_install_name="."
ARG pip_install_extras="[google,sensors,focuser,testing]"

ENV APP_DIR $app_dir
ENV PANUSER $username
ENV USERID $userid
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

WORKDIR "${APP_DIR}"

# Set up user and directories.
RUN useradd -u ${USERID} -o -c "Argus Panoptes" \
        -p panoptes -m -G plugdev,dialout,users,sudo,video,audio ${PANUSER} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    # Setup SSH so localhost works without password.
    mkdir -p "/home/${username}/.ssh" && \
    echo "Host localhost\n\tStrictHostKeyChecking no\n" >> "/home/${username}/.ssh/config" && \
    # Set up directories in PANUSER home.
    mkdir "$image_dir" && chown -R "${USERID}:${USERID}" "$image_dir" && \
    mkdir "$log_dir" && chown -R "${USERID}:${USERID}" "$log_dir" && \
    chown -R "${USERID}:${USERID}" "${APP_DIR}"

 RUN apt-get update && apt-get install -y --no-install-recommends \
         bzip2 ca-certificates wget udev wait-for-it gcc git pkg-config && \
     # Clean up
     apt-get autoremove --purge --yes && \
     apt-get autoclean --yes && \
     apt-get --yes clean && \
     rm -rf /var/lib/apt/lists/*

# Set up arduino cli tools.
RUN echo "Installing arduino-cli from ${arduino_url}" && \
    wget "${arduino_url}_Linux_$(uname -m | sed 's/x86_64/64bit/' | sed 's/aarch64/ARM64/').tar.gz" \
        -O arduino-cli.tar.gz && \
    tar zxvf arduino-cli.tar.gz && \
    mkdir -p "${HOME}/.local/bin" && \
    mv arduino-cli "${HOME}/.local/bin/arduino-cli"  && \
    rm LICENSE.txt && rm arduino-cli.tar.gz

COPY --chown="${USERID}:${USERID}" . .
USER "${USERID}"
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "${pip_install_name}${pip_install_extras}"

# TODO replace with pocs-cli.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "ipython -i scripts/pocs-startup.py" ]
