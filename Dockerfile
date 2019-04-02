FROM gcr.io/panoptes-survey/panoptes-utils
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ENV PANDIR /var/panoptes

COPY . ${POCS}
RUN apt-get update \
    && apt-get --yes install \
        gcc \
        pkg-config \
        libncurses5-dev \
    && rm -rf /var/lib/apt/lists/* \
    && cd ${POCS} \
    && pip3 install --no-cache-dir -r requirements.txt

WORKDIR ${POCS}

CMD ["/bin/bash"]