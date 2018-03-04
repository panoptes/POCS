# PANOPTES development container

FROM ubuntu:16.04
MAINTAINER Developers for PANOPTES project<https://github.com/panoptes/POCS>

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Use "bash" as replacement for	"sh"
# Note: I don't think this is the preferred way to do this anymore
RUN rm /bin/sh && ln -s /bin/bash /bin/sh

RUN apt-get update --fix-missing \
	&& apt-get -y full-upgrade \
	&& apt-get -y install wget bzip2 ca-certificates build-essential sudo python3-numpy git  \
	&& rm -rf /var/lib/apt/lists/*

ARG pan_dir=/var/panoptes

ENV ENV /root/.bashrc
ENV SHELL /bin/bash
ENV PANDIR $pan_dir
ENV PANLOG $PANDIR/logs 
ENV POCS $PANDIR/POCS  
ENV PAWS $PANDIR/PAWS  
ENV PANUSER root

RUN wget --quiet https://raw.githubusercontent.com/panoptes/POCS/develop/scripts/install/install-dependencies.sh -O ~/install-pocs-dependencies.sh \
	&& wget --quiet https://raw.githubusercontent.com/panoptes/POCS/develop/scripts/install/apt-packages-list.txt -O ~/apt-packages-list.txt  \
	&& wget --quiet https://raw.githubusercontent.com/panoptes/POCS/develop/scripts/install/conda-packages-list.txt -O ~/conda-packages-list.txt \
	&& /bin/bash ~/install-pocs-dependencies.sh --no-conda --no-mongodb \
	&& rm ~/install-pocs-dependencies.sh \
	&& rm ~/conda-packages-list.txt \
	&& rm ~/apt-packages-list.txt

# Install miniconda
RUN echo 'export PATH=$PANDIR/astrometry/bin:/opt/conda/bin:$PATH' > /root/.bashrc \
	&& mkdir -p $POCS \
	&& mkdir -p $PAWS \
	&& mkdir -p $PANLOG \
    && wget --quiet https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/anaconda.sh \
    && /bin/bash ~/anaconda.sh -b -p /opt/conda \
    && rm ~/anaconda.sh \
	&& /opt/conda/bin/conda install --yes -c conda-forge jupyterlab

RUN cd $pan_dir \
	&& git clone https://github.com/panoptes/POCS \
	&& cd $POCS && /opt/conda/bin/pip install -Ur requirements.txt \
	&& cd $PANDIR \
	&& git clone https://github.com/panoptes/PAWS \
	&& cd $PAWS && /opt/conda/bin/pip install -Ur requirements.txt

ENV PATH $PANDIR/astrometry/bin:/opt/conda/bin:$PATH

WORKDIR ${POCS}

# Added by PANOPTES install-dependencies.sh
CMD ["/opt/conda/bin/jupyter-lab", "--no-browser", "--ip=0.0.0.0", "--port=9000", "--allow-root"]