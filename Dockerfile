ARG arch=amd64

FROM gcr.io/panoptes-survey/panoptes-utils:$arch
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ARG pandir=/var/panoptes

ENV PANDIR $pandir
ENV POCS ${PANDIR}/POCS

COPY . ${POCS}

RUN apt-get update \
    && apt-get --yes install \
        byobu \
        gcc \
        pkg-config \
        libncurses5-dev \
        vim-nox \
    # GPhoto2
    && wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh \
    && chmod +x gphoto2-updater.sh \
    && /bin/bash gphoto2-updater.sh --stable \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm gphoto2-updater.sh \
    # POCS
    && cd ${POCS} \
    && /opt/conda/envs/panoptes-env/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/conda/envs/panoptes-env/bin/pip install -e . \
    # Link conf_files to $PANDIR
    && ln -s ${POCS}/conf_files/ ${PANDIR}/

WORKDIR ${POCS}

ENTRYPOINT ["resources/docker_files/docker-entrypoint.sh"]

CMD ["/bin/zsh"]

