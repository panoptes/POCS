ARG arch=amd64

FROM gcr.io/panoptes-survey/panoptes-utils:$arch
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ENV PANDIR /var/panoptes

COPY . ${POCS}

RUN apt-get update \
    && apt-get --yes install \
        gcc \
        pkg-config \
        libncurses5-dev \
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
    && /opt/conda/envs/panoptes-env/bin/pip install --no-cache-dir -r requirements.txt

WORKDIR ${POCS}

CMD ["/bin/zsh"]