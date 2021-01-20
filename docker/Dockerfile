FROM ubuntu:latest

LABEL description="Installs the panoptes-pocs module from GitHub."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ARG panuser=pocs-user
ARG userid=1000
ARG pan_dir=/var/panoptes

ENV PANUSER $panuser
ENV USERID $userid
ENV PANDIR $pan_dir

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
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Miniconda
WORKDIR /tmp
RUN wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh" \
        -O install-miniforge.sh && \
    /bin/sh /tmp/install-miniforge.sh -b -f -p /conda && \
    # Initialize conda for the shells.
    /conda/bin/conda init bash

COPY environment.yaml .
RUN /conda/bin/conda env update -n base -f environment.yaml && \
    # Create PANOPTES directories.
    mkdir -p ${PANDIR} && \
    mkdir -p ${PANDIR}/logs && \
    mkdir -p ${PANDIR}/images

ARG pocs_dir="${PANDIR}/POCS"
ENV POCS $pocs_dir
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

ARG pip_extras="[google,testing]"

USER "${userid}"
WORKDIR "${POCS}"
COPY --chown="${userid}:${userid}" . .
RUN echo "Installing editable module with ${pip_extras}" && \
    sudo chown -R ${PANUSER}:${PANUSER} ${PANDIR} && \
    /conda/bin/pip install -e ".${pip_extras}" && \
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
