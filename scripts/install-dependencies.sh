#!/bin/bash -e

THIS_DIR="$(dirname $(readlink -f "${0}"))"
THIS_PROGRAM="$(basename "${0}")"

if [[ -z "${PANDIR}" || -z "${POCS}" || -z "${PAWS}" || -z "${PANLOG}" ||
      -z "${PANUSER}" || ! -d "${PANDIR}" ]] ; then
  echo "Please set the Panoptes environment variables, then re-run this script."
  exit 1
fi

cd "${PANDIR}"

# TODO(jamessynge): Add flags to control behavior, such as skipping apt-get.

ASTROMETRY_VERSION="0.72"
INSTALL_PREFIX="/usr/local"
DO_APT_GET=1
DO_CONDA=1
DO_CFITSIO=1
DO_ASTROMETRY=1
DO_ASTROMETRY_INDICES=1
DO_PIP_REQUIREMENTS=1

function echo_bar() {
  echo <<EOF
################################################################################
EOF
}

# Append $1 to PATH and write command to do the same to .bashrc.
function add_to_PATH() {
  local -r the_dir="$(readlink -f "${1}")"
  echo >>"${HOME}/.bashrc" "
# Added by PANOPTES install-dependencies.sh
PATH=\"${the_dir}:\${PATH}\""
  PATH="${the_dir}:${PATH}"
  echo
  echo "Added ${the_dir} to PATH in .bashrc"
}

# Given the path to a pkg-config file (.pc), extract the version number.
function extract_version_from_pkg_config() {
  if [[ -f "${1}" ]] ; then
    egrep '^Version:' "${1}" | cut '-d:' -f2
  else
    echo ""
  fi
}

# Install miniconda (conda with no additional packages); we can then select
# the set to install.
function install_conda() {
  local -r the_script="${PANDIR}/tmp/miniconda.sh"
  echo_bar
  echo
  echo "Installing miniconda"
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O "${the_script}"
  bash "${the_script}" -b -p "${PANDIR}/miniconda"
  rm "${the_script}"
  add_to_PATH miniconda/bin
}

function install_conda_if_missing() {
  # Intall latest version of Miniconda (Anaconda with
  # fewer packages; any that are needed can then be installed).
  CONDA_BIN="$(which conda)"  # Assuming is a python3 version if found.
  if [[ -z "${CONDA_BIN}" ]] ; then
    install_conda
  fi
}

# Fetches and builds the latest version of cfitsio.
function fetch_and_build_cfitsio() {
  echo_bar
  echo
  echo "Fetching and building latest cfitsio release."
  echo
  # Unpack into PANDIR/tmp/cfitsio
  cd "${PANDIR}"
  mkdir -p tmp/cfitsio
  cd tmp
  rm -rf cfitsio
  wget \
    http://heasarc.gsfc.nasa.gov/FTP/software/fitsio/c/cfitsio_latest.tar.gz \
    -O cfitsio_latest.tar.gz
  tar zxf cfitsio_latest.tar.gz
  cd cfitsio
  ./configure --prefix=${INSTALL_PREFIX}
  make
  make utils stand_alone shared
}

# Print the version of the downloaded and built cfitsio version number, as in
# its pkg-config file (cfitsio.pc).
function latest_cfitsio_version() {
  extract_version_from_pkg_config tmp/cfitsio/cfitsio.pc
}

# Prints the installed cfitsio version number.
function installed_cfitsio_version() {
  pkg-config --mod-version --silence-errors cfitsio || /bin/true
}

# Install the downloaded and built cfitsio.
function sudo_install_cfitsio() {
  echo
  echo "Running sudo make install for cfitsio, you may be prompted for your password."
  echo
  cd "${PANDIR}/tmp/cfitsio"
  (set -x ; sudo make install)
}

# Install the latest versio of cfitsio if it is not already installed.
function install_latest_cfitsio() {
  (fetch_and_build_cfitsio)
  local -r LATEST_CFITSIO_VERSION="$(latest_cfitsio_version)"
  local -r INSTALLED_CFITSIO_VERSION="$(installed_cfitsio_version)"
  if [[ "${LATEST_CFITSIO_VERSION}" == "${INSTALLED_CFITSIO_VERSION}" ]] ; then
    echo "Installed cfitsio is at latest version (${LATEST_CFITSIO_VERSION})."
  else
    if [[ -z "${INSTALLED_CFITSIO_VERSION}" ]] ; then
      echo "Installing cfitsio version ${LATEST_CFITSIO_VERSION}."
    else
      echo "Installing cfitsio version ${LATEST_CFITSIO_VERSION}, replacing" \
        "installed version ${OLD_CFITSIO_VERSION}."
    fi
    (sudo_install_cfitsio)
  fi
  rm -rf tmp/cfitsio_latest.tar.gz tmp/cfitsio
}

# Downloads astrometry version ${ASTROMETRY_VERSION} into a temp directory,
# then builds and installs into ${PANDIR}/astrometry.
# TODO(jamessynge): Discuss whether to build directly in ${PANDIR}/astrometry,
# or instead installing into /usr/local as we do with cfitsio.
function install_astrometry() {
  local -r DIR="astrometry.net-${ASTROMETRY_VERSION}"
  local -r FN="${DIR}.tar.gz"
  local -r URL="http://astrometry.net/downloads/${FN}"
  local -r SCRATCH_DIR="$(mktemp -d "${TMPDIR:-/tmp/}install-astrometry.XXXXXXXXXXXX")"
  local -r INSTALL_TO="${PANDIR}/astrometry"
  cd "${SCRATCH_DIR}"

  echo_bar
  echo  
  echo "Fetching astrometry into directory $(pwd)"

  wget "${URL}"
  tar zxvf "${FN}"
  cd "${DIR}"

  echo "Building ${DIR}"
  make
  make py
  if [[ -d "${INSTALL_TO}" ]] ; then
    rm -rf "${INSTALL_TO}"
  fi
  mkdir -p "${INSTALL_TO}"
  echo "Installing into ${INSTALL_TO}"
  make install "INSTALL_DIR=${INSTALL_TO}"
  echo "add_path ${INSTALL_TO}/data" >> "${INSTALL_TO}/etc/astrometry.cfg"

  add_to_PATH "${INSTALL_TO}/bin"
  cd "${PANDIR}"
  rm -rf "${SCRATCH_DIR}"
}

function install_astrometry_indices() {
  mkdir -p "${PANDIR}/astrometry/data"
  cd "${PANDIR}/astrometry/data"
  if [[ ! -f index-4107.fits ]] ; then
   curl --remote-name \
        http://broiler.astrometry.net/~dstn/4100/index-41[07-19].fits
  fi
  if [[ ! -f astrometry/data/index-4208.fits ]] ; then
    curl --remote-name \
         http://broiler.astrometry.net/~dstn/4200/index-42[08-19].fits
  fi
}

#-------------------------------------------------------------------------------

function show_help() {
  echo "${THIS_PROGRAM} - Install software needed for PANOPTES."
  echo " "
  echo "${THIS_PROGRAM} [options]"
  echo " "
  echo "options:"
  echo "-h, --help               show brief help"
  echo "--no-apt-get             don't run apt-get to install Linux packages"
  echo "--no-cfitsio             don't install the latest version of cfitsio"
  echo "--no-astrometry          don't install astrometry.net software"
  echo "--no-astrometry-indices  don't install astrometry.net indices"
  echo "--no-pip-requirements    don't install python packages"
}

cd "${PANDIR}"
mkdir -p tmp

while test ${#} -gt 0; do
  case "${1}" in
    -h|--help)
      show_help
      exit 0
      ;;
    --no-apt-get)
      DO_APT_GET=0
      shift
      ;;
    --no-cfitsio)
      DO_CFITSIO=0
      shift
      ;;
    --no-conda)
      DO_CONDA=0
      shift
      ;;
    --no-astrometry)
      DO_ASTROMETRY=0
      shift
      ;;
    --no-astrometry-ind*)
      DO_ASTROMETRY_INDICES=0
      shift
      ;;
    --no-pip-requirements)
      DO_PIP_REQUIREMENTS=0
      shift
      ;;
    -x)
      set -x
      shift
      ;;
    *)
      echo "Unknown parameter: ${1}"
      echo
      show_help
      exit 1
      ;;
  esac
done


if [[ "${DO_APT_GET}" -eq 1 ]] ; then
  echo
  echo "Running sudo apt-get install, you may be prompted for your password."
  echo
  (set -x ; sudo apt-get install --yes ${APT_PKGS})
fi


if [[ "${DO_CONDA}" -eq 1 ]] ; then
  install_conda_if_missing
fi


if [[ "${DO_CFITSIO}" -eq 1 ]] ; then
  install_latest_cfitsio
fi


if [[ "${DO_ASTROMETRY}" -eq 1 ]] ; then
  (install_astrometry)
fi


if [[ "${DO_ASTROMETRY_INDICES}" -eq 1 ]] ; then
  (install_astrometry_indices)
fi


if [[ "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  # Upgrade pip itself before installing other python packages.
  pip install -U pip
  pip install -r "${THIS_DIR}/../requirements.txt"
fi

cd "${PANDIR}"
rmdir --ignore-fail-on-non-empty "${PANDIR}/tmp"

exit






exit





  install_astrometry
  
  
  
  
  
  
  
  
  
  
  
fi


if [[ "${DO_ASTROMETRY_INDICES}" -eq 1 ]] ; then
  install_astrometry_indices
fi


set -x
CONDA_BIN=$(which conda)  # Assuming is for python3 if found.
fi





  echo
  echo "Running sudo apt-get install, you may be prompted for your password."
  echo
  (set -x ; sudo apt-get install --yes ${APT_PKGS})
fi












APT_PKGS="$(egrep -v '^#|^ *$' "${THIS_DIR}/apt-packages-list.txt"|sort|uniq)"

cd "${PANDIR}"
mkdir -p tmp

echo
echo "Running sudo apt-get install, you may be prompted for your password."
echo

(set -x ; sudo apt-get install --yes ${APT_PKGS})

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

if [[ ! -f /usr/local/include/fitsio.h ]] ; then
  install_cfitsio() {
    wget \
      http://heasarc.gsfc.nasa.gov/FTP/software/fitsio/c/cfitsio_latest.tar.gz \
      -O tmp/cfitsio_latest.tar.gz
    tar zxf tmp/cfitsio_latest.tar.gz
    cd cfitsio
    ./configure --prefix=/usr/local
    make
    make utils stand_alone shared
    echo
    echo "Running sudo make install for cfitsio, you may be prompted for your password."
    echo
    (set -x ; sudo make install)
    rm tmp/cfitsio_latest.tar.gz
    rmdir --ignore-fail-on-non-empty tmp
  }
  if [[ -d cfitsio ]] ; then
    rm -rf cfitsio
  fi
  (install_cfitsio)
fi

exit


if [[ ! -d astrometry/bin ]] ; then
  # This uses a directory in tmp to download and build astrometry, then
  # installs the binaries into $PANDIR/astrometry.
  install_astrometry() {
    local -r DIR="astrometry.net-${ASTROMETRY_VERSION}"
    local -r FN="${DIR}.tar.gz"
    local -r URL="http://astrometry.net/downloads/${FN}"
    local -r TMP_DIR="$(realpath "${TMPDIR:-${PANDIR}/tmp}")"
    local -r SCRATCH_DIR="$(mktemp -d "${TMP_DIR}/install-astrometry.XXXXXXXXXXXX")"
    local -r INSTALL_TO="${PANDIR}/astrometry"
    cd ${SCRATCH_DIR}
    echo "Fetching astrometry into directory $(pwd)"
    wget "${URL}"
    tar zxvf "${FN}"
    cd "${DIR}" && make && make py && make install "INSTALL_DIR=${INSTALL_TO}"
    echo "add_path ${INSTALL_TO}/data" >> "${INSTALL_TO}/etc/astrometry.cfg"
  }
  mkdir -p astrometry
  (install_astrometry)
fi

if [[ ! -f astrometry/data/index-4107.fits ]] ; then
  mkdir -p astrometry/data
  (cd astrometry/data ;
   curl --remote-name \
     http://broiler.astrometry.net/~dstn/4100/index-41[07-19].fits )
fi

if [[ ! -f astrometry/data/index-4208.fits ]] ; then
  mkdir -p astrometry/data
  (cd astrometry/data ;
   curl --remote-name \
     http://broiler.astrometry.net/~dstn/4200/index-42[08-19].fits )
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
