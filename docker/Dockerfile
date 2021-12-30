ARG image_url=condaforge/miniforge3
ARG image_tag=latest
FROM ${image_url}:${image_tag}

LABEL description="PANOPTES Observatory Control System"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG username=panoptes
ARG userid=1000
ARG app_dir=/pocs
ARG conda_dir=/opt/conda
ARG pip_install_name="."
ARG pip_install_extras="[google,sensors,focuser]"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1
ENV PATH "/home/${username}/.local/bin:$PATH"

RUN apt-get update && apt-get install --no-install-recommends --yes \
        bzip2 ca-certificates wget gcc pkg-config sudo git && \
    # Add user.
    useradd -u ${userid} -o -c "Argus Panoptes" -p panoptes -m -G plugdev,dialout,users,sudo,video,audio ${username} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    # Update conda and install mamba.
    "${conda_dir}/bin/conda" update -n base conda && \
    "${conda_dir}/bin/conda" install mamba && "${conda_dir}/bin/mamba" clean --all --yes && \
    # Set up directories.
    mkdir -p "${app_dir}" && chown -R "${userid}:${userid}" "${app_dir}" && \
    chown -R "${userid}:${userid}" "${conda_dir}"

COPY docker/environment.yaml /tmp/environment.yaml
RUN "${conda_dir}/bin/mamba" env update -n base -f /tmp/environment.yaml && \
    "${conda_dir}/bin/mamba" clean --all --yes

USER "${username}"
WORKDIR "${app_dir}"
COPY --chown="${userid}:${userid}" . .
RUN "${conda_dir}/bin/pip" install --no-cache-dir "${pip_install_name}${pip_install_extras}"

# TODO replace with pocs-cli.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
