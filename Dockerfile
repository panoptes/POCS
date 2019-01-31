# PANOPTES development container

FROM ubuntu:18.04 as build-env
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ARG pan_dir=/var/panoptes

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV ENV /root/.bashrc
ENV SHELL /bin/bash
ENV PANDIR $pan_dir
ENV PANLOG $PANDIR/logs 
ENV POCS $PANDIR/POCS  
ENV PAWS $PANDIR/PAWS  
ENV PANUSER root
ENV SOLVE_FIELD=/usr/bin/solve-field

COPY . /var/panoptes/POCS

# Use "bash" as replacement for "sh"
# Note: I don't think this is the preferred way to do this anymore
RUN rm /bin/sh && ln -s /bin/bash /bin/sh \
    && apt-get update --fix-missing \
    && apt-get -y install \
        astrometry.net \
        byobu \
        bzip2 \
        ca-certificates \
        git \
        wget \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p $PAWS \
    && mkdir -p $POCS \
    && mkdir -p $PANLOG \
    && echo 'export PATH=/opt/conda/bin:$PATH' > /root/.bashrc \
    && wget --quiet https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/anaconda.sh \
    && /bin/bash ~/anaconda.sh -b -p /opt/conda \
    && rm ~/anaconda.sh \
    && cd $POCS \
    && /bin/bash scripts/install/install-dependencies.sh --no-conda --no-mongodb \
    && /opt/conda/bin/pip install -Ur requirements.txt \
    && /opt/conda/bin/pip install -e . \
    && cd $PANDIR \
    && /opt/conda/bin/conda clean --all --yes

WORKDIR ${POCS}

CMD ["/bin/bash"]