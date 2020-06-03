ARG BASE_IMAGE=panoptes-pocs:develop
FROM ${BASE_IMAGE}

LABEL description="Installs the local folder in develop mode (i.e. pip install .e). \
and installs a number of developer tools. Runs jupyter lab instance. This assumes the \
`panoptes-pocs:develop` has already been built locally."
LABEL maintainers="developers@projectpanoptes.org"
LABEL repo="github.com/panoptes/POCS"

ARG panuser=panoptes
ARG userid=1000
ARG pan_dir=/var/panoptes
ARG pocs_dir="${pan_dir}/POCS"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV SHELL /bin/zsh

ENV USERID $userid
ENV PANDIR $pan_dir
ENV PANLOG "$pan_dir/logs"
ENV PANUSER $panuser
ENV POCS $pocs_dir
ENV PATH "/home/${PANUSER}/.local/bin:$PATH"

RUN apt-get update && \
    # Node for jupyterlab.
    curl -sL https://deb.nodesource.com/setup_12.x | bash - && \
    # Make a developer's life easier.
    apt-get install -y --no-install-recommends \
        wget curl bzip2 ca-certificates nano neovim \
        gcc git pkg-config ncdu sudo nodejs && \
    echo "$PANUSER ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers


USER $PANUSER
# Can't seem to get around the hard-coding
COPY --chown=panoptes:panoptes . ${PANDIR}/POCS/
RUN cd ${PANDIR}/POCS && \
    # Install everything!
    pip install -e ".[google,developer,plotting,testing]" && \
    # Set some jupyterlab defaults.
    mkdir -p /home/panoptes/.jupyter && \
    jupyter-lab --generate-config && \
    # Jupyterlab extensions.
    echo "c.JupyterApp.answer_yesBool = True" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    echo "c.JupyterApp.open_browserBool = False" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    echo "c.JupyterAppy.notebook_dir = '${PANDIR}'" >> \
        "/home/panoptes/.jupyter/jupyter_notebook_config.py" && \
    jupyter labextension install @pyviz/jupyterlab_pyviz \
                                jupyterlab-drawio \
                                @aquirdturtle/collapsible_headings \
                                @telamonian/theme-darcula

USER root

# Cleanup apt.
RUN apt-get autoremove --purge -y && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${PANDIR}

# Start a jupyterlab instance.
CMD ["/home/panoptes/.local/bin/jupyter-lab"]
