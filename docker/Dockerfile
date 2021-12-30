ARG image_url=condaforge/miniforge3
ARG image_tag=latest
FROM ${image_url}:${image_tag}

LABEL description="PANOPTES Observatory Control System (POCS) Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG username=pocs-user
ARG userid=1000
ARG app_dir=/panoptes-pocs
ARG conda_dir=/opt/conda
ARG pip_install_name="."
ARG pip_install_extras="[google,sensors,focuser]"

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
    # Set up directories.
    mkdir -p "${app_dir}" && chown -R "${userid}:${userid}" "${app_dir}" && \
    # Install mamba.
    "${conda_dir}/bin/conda" install mamba && "${conda_dir}/bin/mamba" clean --all --yes

COPY docker/environment.yaml /tmp/environment.yaml
RUN "${conda_dir}/bin/mamba" env update -n base -f /tmp/environment.yaml && \
    "${conda_dir}/bin/mamba" clean --all --yes

USER "${username}"
WORKDIR "${app_dir}"
COPY --chown="${userid}:${userid}" . .
RUN /opt/conda/bin/pip install --no-cache-dir "${pip_install_name}${pip_install_extras}" && \
    sudo apt-get autoremove --purge --yes && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

# TODO replace with pocs-cli.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
