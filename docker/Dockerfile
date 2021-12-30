ARG image_url=python
ARG image_tag=slim-buster
FROM ${image_url}:${image_tag}

LABEL description="PANOPTES Observatory Control System (POCS) Service"
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG username=panoptes
ARG userid=1000
ARG app_dir=/pocs
ARG pip_install_name="."
ARG pip_install_extras="[google,sensors,focuser]"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install --no-install-recommends --yes \
        bzip2 ca-certificates wget gcc pkg-config sudo git && \
    # Add user.
    useradd -u ${userid} -o -c "Argus Panoptes" -p panoptes -m -G plugdev,dialout,users,sudo,video,audio ${username} && \
    # Allow sudo without password.
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER "${username}"
WORKDIR "${app_dir}"
COPY --chown="${userid}:${userid}" . .
RUN pip install --no-cache-dir "${pip_install_name}${pip_install_extras}"

# TODO replace with pocs-cli.
ENTRYPOINT [ "/usr/bin/env", "bash", "-ic" ]
