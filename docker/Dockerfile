ARG image_url=python
ARG image_tag=slim-buster
FROM ${image_url}:${image_tag}

LABEL description="PANOPTES Observatory Control System (POCS) Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG username=pocs-user
ARG userid=1000
ARG app_dir=/panoptes-pocs
ARG image_dir=/images
ARG log_dir=/logs
ARG pip_install_name="."
ARG pip_install_extras="[google,sensors,focuser,testing]"
ARG arduino_url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest"
ARG conda_url_base="https://github.com/conda-forge/miniforge/releases/latest/download"

ENV APP_DIR $app_dir
ENV PANUSER $username
ENV USERID $userid
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install --no-install-recommends --yes \
        bzip2 ca-certificates wget gcc pkg-config sudo git && \
    # Add user.
    useradd -u ${userid} -o -c "Argus Panoptes" -p panoptes -m -G plugdev,dialout,users,sudo,video,audio ${username} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    # Setup SSH so localhost works without password.
    mkdir -p "/home/${username}/.ssh" && \
    echo "Host localhost\n\tStrictHostKeyChecking no\n" >> "/home/${username}/.ssh/config" && \
    # Set up directories.
    mkdir "$image_dir" && chown -R "${userid}:${userid}" "$image_dir" && \
    mkdir "$log_dir" && chown -R "${userid}:${userid}" "$log_dir" && \
    mkdir -p "${app_dir}" && chown -R "${userid}:${userid}" "${app_dir}"

# Set up arduino cli tools.
RUN echo "Installing arduino-cli from ${arduino_url}" && \
    wget "${arduino_url}_Linux_$(uname -m | sed 's/x86_64/64bit/' | sed 's/aarch64/ARM64/').tar.gz" \
        -O arduino-cli.tar.gz && \
    tar zxvf arduino-cli.tar.gz && \
    mkdir -p "~/.local/bin" && \
    mv arduino-cli "~/.local/bin/arduino-cli"  && \
    rm LICENSE.txt && rm arduino-cli.tar.gz

USER "${username}"
COPY docker/environment.yaml /tmp/environment.yaml
# Install microconda, initialize, and install mamba.
RUN wget "${conda_url_base}/Miniforge3-Linux-$(uname -m).sh" && \
    bash "Miniforge3-Linux-$(uname -m).sh" -b -p /opt/conda && \
    /opt/conda/bin/conda init bash && \
    /opt/conda/bin/conda install mamba && \
    /opt/conda/bin/mamba install -y -n base -f /tmp/environment.yaml && \
    /opt/conda/bin/mamba clean --all --yes

WORKDIR "${APP_DIR}"
COPY --chown="${userid}:${userid}" . .
RUN /opt/conda/bin/pip install --no-cache-dir "${pip_install_name}${pip_install_extras}" && \
    apt-get autoremove --purge --yes && \
    apt-get autoclean --yes && \
    apt-get --yes clean && \
    rm -rf /var/lib/apt/lists/*

# TODO replace with pocs-cli.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "ipython -i scripts/pocs-startup.py" ]
