FROM ubuntu:latest
MAINTAINER Wilfred Tyler Gee <wtylergee@gmail.com>

# Versions for software
ENV CDS_VERSION 3.80
ENV SCAMP_VERSION 2.0.4

### "localedef"
RUN locale-gen en_US.UTF-8

### "apt-defaults"
RUN echo "APT::Get::Assume-Yes true;" >> /etc/apt/apt.conf.d/80custom ; \
    echo "APT::Get::Quiet true;" >> /etc/apt/apt.conf.d/80custom ; \
    apt-get update

RUN apt-get update && apt-get install \
  ack-grep \
  adduser \
  aptitude \
  build-essential \
  curl \
  fftw3 \
  fftw3-dev \
  git \
  htop \
  libatlas-base-dev \
  libatlas-dev \
  libplplot-dev \
  man-db \
  mongodb \
  openssh-server \
  pkg-config \
  rsync \
  sextractor \
  strace \
  sudo \
  tree \
  unzip \
  vim \
  wget \
    ;

WORKDIR /tmp
RUN echo "Updating gphoto2"; \
  wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh && \
  chmod +x gphoto2-updater.sh && \
  sudo ./gphoto2-updater.sh

WORKDIR /tmp
RUN echo "Installing cdsclient"; \
  wget http://cdsarc.u-strasbg.fr/ftp/pub/sw/cdsclient.tar.gz && \
  tar -zxvf cdsclient.tar.gz && \
  cd cdsclient-$CDS_VERSION && \
  ./configure && \
  make && sudo make install 
  
WORKDIR /tmp  
RUN echo "Installing SCAMP"; \
  wget http://www.astromatic.net/download/scamp/scamp-$SCAMP_VERSION.tar.gz && \
  tar -zxvf scamp-$SCAMP_VERSION.tar.gz && cd scamp-$SCAMP_VERSION && \
  ./configure \
    --with-atlas-libdir=/usr/lib/atlas-base \
    --with-atlas-incdir=/usr/include/atlas \
    --with-fftw-libdir=/usr/lib \
    --with-fftw-incdir=/usr/include \
    --with-plplot-libdir=/usr/lib \
    --with-plplot-incdir=/usr/include/plplot && \
  make && sudo make install

RUN apt-get update && apt-get install \
  astrometry.net \
  swarp \
    ;

RUN echo "Getting astrometry.net indicies (this might take a while)"; \
  cd /usr/share/data && \
  sudo wget -A fits -m -l 1 -nd http://broiler.astrometry.net/~dstn/4100/

RUN groupadd -r panoptes && useradd -r -m -g panoptes panoptes && \
    echo "panoptes:password" | chpasswd ; \
    echo "panoptes ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/panoptes

ENV HOME /home/panoptes
USER panoptes

RUN mkdir /var/panoptes && \
  chown -R panoptes:panoptes /var/panoptes
  
ENV PANDIR /var/panoptes

WORKDIR /home/panoptes
