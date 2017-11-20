#!/bin/bash -e

# TODO(jamessynge): Add flags to control behavior, such as skipping apt-get.

if [[ -z "${PANDIR}" || -z "${POCS}" || -z "${PAWS}" || -z "${PANLOG}" ||
      -z "${PANUSER}" || ! -d "${PANDIR}" ]] ; then
  echo "Please set the Panoptes environment variables, then re-run this script."
  exit 1
fi

THIS_DIR="$(dirname $(readlink -f "${0}"))"
APT_PKGS="$(egrep -v '^#|^ *$' "${THIS_DIR}/apt-packages-list.txt"|sort|uniq)"

cd "${PANDIR}"
mkdir -p tmp

echo
echo "Running sudo apt-get install, you may be prompted for your password."
echo

(set -x ; sudo apt-get install --yes ${APT_PKGS})

add_to_PATH() {
  local -r the_dir="$(readlink -f "${1}")"
  echo >>"${HOME}/.bashrc" "
# Added by PANOPTES install-dependencies.sh
PATH=\"${the_dir}:\${PATH}\""
  PATH="${the_dir}:${PATH}"
}

# If conda is not present, install latest version of Miniconda (Anaconda with
# fewer packages; any that are needed can then be installed).
set -x
CONDA_BIN=$(which conda)  # Assuming is for python3 if found.
if [[ -z "${CONDA_BIN}" ]] ; then
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O tmp/miniconda.sh
  bash tmp/miniconda.sh -b -p "${PANDIR}/miniconda"
  rm tmp/miniconda.sh
  add_to_PATH miniconda/bin
fi

if [[ ! -d cfitsio ]] ; then
  wget \
    http://heasarc.gsfc.nasa.gov/FTP/software/fitsio/c/cfitsio_latest.tar.gz \
    -O tmp/cfitsio_latest.tar.gz
  tar zxf tmp/cfitsio_latest.tar.gz
  cd cfitsio
  ./configure
  make
  make utils stand_alone shared
fi

# Upgrade pip itself before installing other python packages.
pip install -U pip
pip install -r "${THIS_DIR}/../requirements.txt"

exit

- cd cfitsio
- ./configure
- make
- make fpack
- make funpack
- sudo make install






exit

dist: trusty
sudo: required
language: python
services:
  - mongodb
python:
  - "3.6"
cache:
  - pip
env:
  - POCS=$TRAVIS_BUILD_DIR PANDIR=/var/panoptes
before_install:
    - sudo mkdir /var/panoptes && sudo chmod 777 /var/panoptes
    - mkdir $PANDIR/logs
    - ln -s $TRAVIS_BUILD_DIR /var/panoptes/POCS
    - pip install coveralls
    - pip install -U pip
    - cd $HOME
    - wget http://heasarc.gsfc.nasa.gov/FTP/software/fitsio/c/cfitsio_latest.tar.gz
    - tar zxf cfitsio_latest.tar.gz
    - cd cfitsio
    - ./configure
    - make
    - make fpack
    - make funpack
    - sudo make install
    - sudo mkdir -p /var/panoptes/astrometry/data
    - sudo chmod -R 777 /var/panoptes/astrometry/
addons:
  apt:
    packages:
    - gphoto2
    - libcairo2-dev 
    - libnetpbm10-dev 
    - netpbm
    - libpng12-dev
    - libjpeg-dev
    - python-numpy
    - python-pyfits
    - python-dev 
    - zlib1g-dev 
    - libbz2-dev 
    - swig 
    - cfitsio-dev
install:
  - wget http://astrometry.net/downloads/astrometry.net-0.72.tar.gz
  - tar zxvf astrometry.net-0.72.tar.gz
  - cd astrometry.net-0.72 && make && make py && make install INSTALL_DIR=/var/panoptes/astrometry
  - echo 'add_path /var/panoptes/astrometry/data' | sudo tee --append /var/panoptes/astrometry/etc/astrometry.cfg
  - wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh;
  - bash miniconda.sh -b -p $HOME/miniconda
  - export PATH="$HOME/miniconda/bin:$HOME/cfitsio/bin:/var/panoptes/astrometry/bin:$PATH"
  - hash -r

  - conda config --set always_yes yes --set changeps1 no
  - conda update -q conda
  - conda info -a # Useful for debugging any issues with conda
  - conda create -q -n test-environment python=$TRAVIS_PYTHON_VERSION
  - source activate test-environment

  - cd $TRAVIS_BUILD_DIR
  - pip install -r requirements.txt
  - python setup.py install
script:
  - coverage run setup.py test
  - coverage combine .coverage*
after_success:
    - if [[ $TRAVIS_PYTHON_VERSION == 3.6* ]]; then
          bash <(curl -s https://codecov.io/bash);
      fi
