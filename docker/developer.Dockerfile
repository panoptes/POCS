ARG BASE_IMAGE=panoptes-pocs:develop
FROM ${BASE_IMAGE}

LABEL description="Installs a number of developer tools. Runs jupyter lab instance. \
This assumes the `panoptes-pocs:develop` has already been built locally."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG panuser=panoptes
ARG userid=1000
ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"
ARG conda_env_name="panoptes"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh

ENV USERID $userid
ENV PANDIR $pan_dir
ENV PANLOG "$pan_dir/logs"
ENV PANUSER $panuser
ENV POCS $pocs_dir

RUN apt-get update && \
    # Make a developer's life easier.
    apt-get install --yes --no-install-recommends \
        bzip2 ca-certificates nano neovim \
        ncdu htop

USER $PANUSER
RUN echo "Installing developer tools" && \
    "${PANDIR}/conda/bin/conda" install --name "${conda_env_name}" \
        altair \
        bokeh \
        jupyterlab \
        holoviews \
        hvplot \
        nodejs \
        seaborn && \
    # Set some jupyterlab defaults.
    mkdir -p /home/panoptes/.jupyter && \
    /usr/bin/env zsh -c "${PANDIR}/conda/envs/${conda_env_name}/bin/jupyter-lab --no-browser --generate-config" && \
    # Jupyterlab extensions.
    echo "c.JupyterApp.answer_yes = True" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    echo "c.JupyterApp.open_browser = False" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    echo "c.JupyterApp.notebook_dir = '${PANDIR}'" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    # Cleanup
    sudo apt-get autoremove --purge --yes && \
    sudo apt-get autoclean --yes && \
    sudo rm -rf /var/lib/apt/lists/*

USER root
WORKDIR ${PANDIR}