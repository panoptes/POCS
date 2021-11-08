ARG image_url=gcr.io/panoptes-exp/panoptes-utils
ARG image_tag=develop
FROM ${image_url}:${image_tag} AS pocs-base

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/bash
ENV PYTHONUNBUFFERED 1

ENV POCS "/panoptes-pocs"
ARG app_dir=/panoptes-pocs
ENV APP_DIR $app_dir

ARG userid=1000
ARG pip_extras="[google,testing]"

WORKDIR "${APP_DIR}"
USER "${userid}"

# Set up some common directories.
RUN sudo apt-get update && \
    sudo apt-get install -y --no-install-recommends gphoto2 && \
    sudo chown -R "${userid}:${userid}" "${APP_DIR}"

COPY --chown="${userid}:${userid}" . .
RUN echo "Installing module with ${pip_extras}" && \
    pip install -e ".${pip_extras}"

CMD [ "pytest" ]
