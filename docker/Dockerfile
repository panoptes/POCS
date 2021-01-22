FROM ubuntu:latest

LABEL description="Installs the panoptes-pocs module from GitHub."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ARG panuser=pocs-user
ARG userid=1000
ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"
ARG pip_install_extras="[google,testing]"

ENV PANUSER $panuser
ENV USERID $userid
ENV PANDIR $pan_dir
ENV POCS $pocs_dir

# Install system dependencies.
RUN apt-get update && apt-get install --no-install-recommends --yes \
        bzip2 ca-certificates \
        wget gcc git pkg-config sudo gosu less udev \
        astrometry.net astrometry-data-tycho2-10-19 dcraw exiftool \
        libcfitsio-dev libcfitsio-bin \
        libfreetype6-dev libpng-dev libjpeg-dev libffi-dev \
        gphoto2 && \
    useradd -u ${USERID} -o -c "PANOPTES POCS" \
        -p panoptes -m -G plugdev,dialout,users,sudo ${PANUSER} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    # Setup SSH so localhost works without password
    mkdir -p "/home/${panuser}/.ssh" && \
    echo "Host localhost\n\tStrictHostKeyChecking no\n" >> "/home/${panuser}/.ssh/config"

USER "${userid}"

# Miniconda
WORKDIR /tmp
RUN echo "Installing conda via miniforge" && \
    sudo mkdir -p /conda && \
    sudo chown -R "${PANUSER}:${PANUSER}" /conda && \
    # Miniforge
    wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh" \
        -O install-miniforge.sh && \
    /bin/sh install-miniforge.sh -b -f -p /conda && \
    # Initialize conda for the shells.
    /conda/bin/conda init bash

ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

RUN echo "Setting up filesystem and installing conda." && \
    # Create PANOPTES directories.
    sudo mkdir -p ${PANDIR} && \
    sudo chown -R "${PANUSER}:${PANUSER}" ${PANDIR} && \
    mkdir -p ${PANDIR}/logs && \
    mkdir -p ${PANDIR}/images && \
    mkdir -p ${POCS}

COPY environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml

WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .
RUN echo "Installing editable module with ${pip_install_extras}" && \
    /conda/bin/pip install -e ".${pip_install_extras}" && \
    # Remove git folder
    rm -rf "${POCS}/.git" && \
    # Cleanup
    sudo apt-get autoremove --purge --yes && \
    sudo apt-get autoclean --yes && \
    sudo apt-get --yes clean && \
    sudo rm -rf /var/lib/apt/lists/*

USER root
ENTRYPOINT ["/bin/sh", "/var/panoptes/POCS/scripts/entrypoint.sh"]
CMD [ "/bin/bash" ]
