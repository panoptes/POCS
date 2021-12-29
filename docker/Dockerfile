ARG image_url=mambaorg/micromamba
ARG image_tag=latest
FROM ${image_url}:${image_tag} AS panoptes-pocs-base

LABEL description="Installs the dependencies for panoptes-pocs."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/panoptes-pocs"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1

ARG panuser=pocs-user
ARG userid=1000
ARG app_dir=/panoptes-pocs
ARG pip_install_name="."
ARG pip_install_extras=""

ENV APP_DIR $app_dir
ENV PANUSER $panuser
ENV USERID $userid
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

# Install system dependencies as root user.
USER root
RUN echo "Building from ${image_url}:${image_tag}" && \
    apt-get update && apt-get install --no-install-recommends --yes \
        bzip2 ca-certificates \
        wget gcc pkg-config sudo less udev wait-for-it \
        dcraw exiftool git \
        libcfitsio-dev libcfitsio-bin \
        libfreetype6-dev libpng-dev libjpeg-dev libffi-dev && \
    apt-get autoremove --purge --yes && \
    apt-get autoclean --yes && \
    apt-get --yes clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Change username.
    usermod -l ${panuser} micromamba && \
    usermod -aG plugdev,dialout,users,sudo ${panuser} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    # Setup SSH so localhost works without password.
    mkdir -p "/home/${panuser}/.ssh" && \
    echo "Host localhost\n\tStrictHostKeyChecking no\n" >> "/home/${panuser}/.ssh/config"

USER "${panuser}"
COPY docker/environment.yaml /tmp/environment.yaml
RUN echo "Updating python environment." && \
    micromamba install -y -n base -f /tmp/environment.yaml && \
    micromamba clean --all --yes

WORKDIR "${APP_DIR}"
COPY --chown="${userid}:${userid}" . .
RUN echo "Installing panoptes-pocs module with ${pip_install_extras}" && \
    pip install "${pip_install_name}${pip_install_extras}" && \
    # Cleanup.
    pip cache purge && \
    sudo apt purge -y git

# We are still the PANUSER.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
CMD [ "panoptes-config-server", "--help" ]
