#!/bin/bash -e

# Run with --help to see your options. With no options, does a complete install
# of dependencies, though attempts to reuse existing installs.

THIS_DIR="$(dirname $(readlink -f "${0}"))"
THIS_PROGRAM="$(basename "${0}")"

if [[ -z "${PANDIR}" || -z "${POCS}" || -z "${PAWS}" || -z "${PANLOG}" ||
      -z "${PANUSER}" ]] ; then
  echo "Please set the Panoptes environment variables, then re-run this script."
  exit 1
fi

mkdir -p "${PANDIR}"
cd "${PANDIR}"

ASTROMETRY_VERSION="0.72"
INSTALL_PREFIX="/usr/local"

DO_APT_GET=1
DO_MONGODB=1
DO_CONDA=1
DO_REBUILD_CONDA_ENV=0
DO_INSTALL_CONDA_PACKAGES=1
DO_CFITSIO=0  # Disabled in favor of installing with apt-get.
DO_ASTROMETRY=1
DO_ASTROMETRY_INDICES=1
DO_PIP_REQUIREMENTS=1

# Which bash file do we need to modify? The last found here is the one that
# bash executes for login shells, and so provides the environment for
# all processes under that.
THE_PROFILE="${HOME}/.profile"
if [[ -f "${HOME}/.bash_login" ]] ; then
  THE_PROFILE="${HOME}/.bash_login"
fi
if [[ -f "${HOME}/.bash_profile" ]] ; then
  THE_PROFILE="${HOME}/.bash_profile"
fi

function echo_bar() {
  if [[ -n "$(which resize)" ]] ; then
    eval $(resize|grep COLUMNS=)
  elif [[ -n "$(which stty)" ]] ; then
    COLUMNS="$(stty size | cut '-d ' -f2)"
  fi
  printf "%${COLUMNS:-80}s\n" | tr ' ' '#'
}

function ensure_profile_exists() {
  if [[ ! -f "${THE_PROFILE}" ]] ; then
    touch "${THE_PROFILE}"
  fi
}

function profile_contains_text() {
  local -r target_text="${1}"
  if [[ -n "$(fgrep -- "${target_text}" "${THE_PROFILE}")" ]] ; then
    return 0
  else
    return 1
  fi
}

function add_to_profile_before_target() {
  local -r new_text="${1}"
  local -r target_text="${2}"
  if profile_contains_text "${new_text}" ; then
    echo "Already in ${THE_PROFILE}: ${new_text}"
    return 0
  fi
  ensure_profile_exists
  # This backup is just for debugging (i.e. showing the before and after
  # diff).
  local -r the_backup="$(mktemp "${THE_PROFILE}.pre-edit.XXXXX")"
  cp -p "${THE_PROFILE}" "${the_backup}"
  if profile_contains_text "${target_text}" ; then
    # Add just before the target text.
    sed -i "/${target_text}/i \
# Added by PANOPTES install-dependencies.sh\n\
${new_text}\n" "${THE_PROFILE}"
  else
    # Append to the end of the file.
    echo >>"${THE_PROFILE}" "
# Added by PANOPTES install-dependencies.sh
${new_text}"
  fi
  # Again, this diff is just for debugging.
  echo "Modified ${THE_PROFILE}:"
  echo
  diff -u "${the_backup}" "${THE_PROFILE}" || /bin/true
  echo
  rm "${the_backup}"
}

# Add $1 to .profile before where bashrc is invoked.
# This assumes a standard (default) .profile.
function add_to_profile_before_bashrc() {
  add_to_profile_before_target "${1}" "# if running bash"
}

# Append $1 to PATH and write command to do the same to .profile.
function add_to_PATH() {
  local -r the_dir="$(readlink -f "${1}")"
  add_to_profile_before_bashrc "PATH=\"${the_dir}:\${PATH}\""
  PATH="${the_dir}:${PATH}"

  return 0

  local -r the_file="${HOME}/.profile"
  ensure_profile_exists
  if [[ -z "$(egrep -- "PATH=.*${the_dir}" "${the_file}")" ]] ; then
    echo >>"${the_file}" "
# Added by PANOPTES install-dependencies.sh
PATH=\"${the_dir}:\${PATH}\""
    PATH="${the_dir}:${PATH}"
    echo
    echo "Added ${the_dir} to PATH in ${the_file}"
  else
    echo "${the_file} already adds ${the_dir} to PATH"
  fi
}

# Given the path to a pkg-config file (.pc), extract the version number.
function extract_version_from_pkg_config() {
  if [[ -f "${1}" ]] ; then
    egrep '^Version:' "${1}" | cut '-d:' -f2
  else
    echo ""
  fi
}

function install_apt_packages() {
  # Remove all the comments from the package list and install the packages whose
  # names are left.
  APT_PKGS="$(cut '-d#' -f1 "${THIS_DIR}/apt-packages-list.txt" | sort | uniq)"
  echo
  echo "Running sudo apt-get install, you may be prompted for your password."
  echo
  (set -x ; sudo apt-get update)
  (set -x ; sudo apt-get install --yes ${APT_PKGS})
}

function install_mongodb() {
  # This is based on https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/
  # Note this function does not configure mongodb itself, i.e. no users or
  # security settings.
  echo_bar
  local MONGO_KEY=""
  local MONGO_URL="http://repo.mongodb.org/apt/ubuntu"
  local MONGO_VERSION=""
  local MONGO_SOURCE_PATH=""
  local LSB_RELEASE=""
  if [[ -n "$(which lsb_release)" ]] ; then
    LSB_RELEASE="$(lsb_release -sc)"
  fi
  if [[ "${LSB_RELEASE}" = "xenial" ]] ; then
    MONGO_KEY=2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
    MONGO_VERSION=3.6
  elif [[ "${LSB_RELEASE}" = "bionic" ]] ; then
    MONGO_KEY=9DA31620334BD75D9DCB49F368818C72E52529D4
    MONGO_VERSION=4.0
  else
    echo "ERROR: don't know which version of MongoDB to install."
    return 1
  fi
  MONGO_URL+=" ${LSB_RELEASE}/mongodb-org/${MONGO_VERSION}"
  MONGO_SOURCE_PATH="/etc/apt/sources.list.d/mongodb-org-${MONGO_VERSION}.list"

  echo "
Installing MongoDB ${MONGO_VERSION}, for which several commands require sudo,
so you may be prompted for you password. Starting by telling APT where to find
the MongoDB packages.
"
  sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv ${MONGO_KEY}
  echo "deb ${MONGO_URL} multiverse" | sudo tee "${MONGO_SOURCE_PATH}"
  echo "
Updating the list of packages so APT finds the MongoDB packages,
then installing MongoDB.
"
  sudo apt-get update
  sudo apt-get install -y mongodb-org
  echo "
MongoDB is installed, now updating the config and starting mongod.
"
  echo "[Unit]
Description=High-performance, schema-free document-oriented database
After=network.target
Documentation=https://docs.mongodb.org/manual

[Service]
User=mongodb
Group=mongodb
ExecStart=/usr/bin/mongod --quiet --config /etc/mongod.conf

[Install]
WantedBy=multi-user.target" | sudo tee /lib/systemd/system/mongod.service

  sudo systemctl daemon-reload
  sudo systemctl start mongod
  sudo systemctl enable mongod
}

function maybe_install_mongodb() {
  if [[ -z "$(which mongo)" || -z "$(systemctl | grep mongo)" ]] ; then
    install_mongodb
  fi
}

# Install miniconda (conda with no additional packages); we can then select
# the set to install.
function install_conda() {
  local -r the_script="${PANDIR}/tmp/miniconda.sh"
  local -r the_destination="${PANDIR}/miniconda"
  if [[ -d "${the_destination}" ]] ; then
    echo_bar
    echo
    echo "Removing previous miniconda installation from ${the_destination}"
    rm -rf "${the_destination}"
  fi
  echo_bar
  echo
  echo "Installing miniconda. License at: https://conda.io/docs/license.html"
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O "${the_script}"
  bash "${the_script}" -b -p "${the_destination}"
  rm "${the_script}"

  # As per the Anaconda 4.4 release notes, one is supposed to add the following
  # to .bash_profile, .bashrc or whereever is appropriate:
  #    . $CONDA_LOCATION/etc/profile.d/conda.sh
  #    conda activate base
  # Where CONDA_LOCATION is where Anaconda or miniconda was installed.
  # We do the first step here, but obviously only we we are actually
  # installing conda. The second step will be done unconditionally
  # elsewhere in this file.

  . ${the_destination}/etc/profile.d/conda.sh
  add_to_profile_before_bashrc \
      ". ${the_destination}/etc/profile.d/conda.sh"
}

function install_conda_if_missing() {
  # Intall latest version of Miniconda (Anaconda with
  # fewer packages; any that are needed can then be installed).
  # Note that if conda is found, we assume that a Python 3 version is installed.
  if [[ -z "$(which conda)" ]] ; then
    install_conda
  else
    echo_bar
    echo
    echo "Reusing existing conda:" "$(which conda)"
  fi
}

# Fetches and configures the latest version of cfitsio; this allows us to
# extract the version from the package config file (cfitsio.pc).
function fetch_and_configure_cfitsio() {
  echo_bar
  echo
  echo "Fetching and configuring latest cfitsio release..."
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
}

# Builds the downloaded version of cfitsio.
function build_cfitsio() {
  echo
  echo "Building cfitsio..."
  echo
  cd "${PANDIR}/tmp/cfitsio"
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
  (fetch_and_configure_cfitsio)
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
    (build_cfitsio)
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

  add_to_PATH "${INSTALL_TO}/bin"
  cd "${PANDIR}"
  rm -rf "${SCRATCH_DIR}"
}

function install_astrometry_indices() {
  mkdir -p "${PANDIR}/astrometry/data"
  python "${POCS}/pocs/utils/data.py"
}

#-------------------------------------------------------------------------------

function show_help() {
  echo "${THIS_PROGRAM} - Install software needed for PANOPTES."
  echo " "
  echo "${THIS_PROGRAM} [options]"
  echo " "
  echo "options:"
  echo "-h, --help                 show brief help"
  echo "-x                         turn on bash debug output"
  echo "--run <function>           run the named function and exit, for debugging"
  echo "--no-apt-get               don't run apt-get to install Linux packages"
  echo "--no-mongodb               don't install and start mongodb server"
  echo "--no-cfitsio               don't install the latest version of cfitsio"
  echo "--no-conda                 don't install the latest version of Anaconda"
  echo "--no-conda-packages        don't install packages into Anaconda"
  echo "--rebuild-conda-env        rebuild the panoptes-env"
  echo "--no-astrometry            don't install astrometry.net software"
  echo "--no-astrometry-indices    don't install astrometry.net indices"
  echo "--no-pip-requirements      don't install python packages"
}

cd "${PANDIR}"
mkdir -p tmp

while test ${#} -gt 0; do
  case "${1}" in
    -h|--help)
      show_help
      exit 0
      ;;
    -x)
      set -x
      shift
      ;;
    --run)
      if [ $# -lt 2 ]; then
        echo "Function name missing after ${1}."
        show_help
        exit 1
      fi
      shift
      (${1})
      exit
      ;;
    --no-apt-get)
      DO_APT_GET=0
      shift
      ;;
    --no-mongodb)
      DO_MONGODB=0
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
    --rebuild-conda-env)
      DO_REBUILD_CONDA_ENV=1
      shift
      ;;
    --no-conda-packages)
      DO_INSTALL_CONDA_PACKAGES=0
      shift
      ;;
    --no-pip-requirements)
      DO_PIP_REQUIREMENTS=0
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
    *)
      echo "Unknown parameter: ${1}"
      echo
      show_help
      exit 1
      ;;
  esac
done


if [[ "${DO_APT_GET}" -eq 1 ]] ; then
  install_apt_packages
fi


if [[ "${DO_MONGODB}" -eq 1 ]] ; then
  maybe_install_mongodb
fi


if [[ "${DO_CONDA}" -eq 1 ]] ; then
  install_conda_if_missing
fi

# Add the astropy channel, i.e. an additional repository in which to
# look for packages. With conda 4.1.0 and later, by default the highest
# priority repository that contains a package is used as the source for
# that package, even if there is a newer version in a lower priority
# package. And by default the most recently added repository is treated
# as the highest priority repository. Here we use prepend to be clear
# that we want astropy to be highest priority.
conda config --add channels astropy

# Use the base Anaconda environment until we're ready to
# work with the PANOPTES environment.
conda activate base

# Make sure we use the correct Anaconda environment.
DO_CREATE_CONDA_ENV=0
if [[ -z "$(conda env list | grep panoptes-env)" ]] ; then
  DO_CREATE_CONDA_ENV=1
elif [[ "${DO_REBUILD_CONDA_ENV}" -eq 1 ]] ; then
  echo_bar
  echo 
  echo "Removing previous PANOPTES conda env"
  conda remove --all --yes --quiet -n panoptes-env
  DO_CREATE_CONDA_ENV=1
fi

if [[ "${DO_CONDA}" -eq 1 || "${DO_CREATE_CONDA_ENV}" -eq 1 || \
      "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Updating base conda installation."
  conda update --quiet --yes -n base conda
fi

if [[ "${DO_CREATE_CONDA_ENV}" -eq 1 ]] ; then
  echo_bar
  echo 
  echo "Creating conda env for PANOPTES: panoptes-env"
  conda create --yes -n panoptes-env python=3
fi

add_to_profile_before_bashrc "conda activate panoptes-env"
conda activate panoptes-env

if [[ "${DO_CONDA}" -eq 1 || "${DO_CREATE_CONDA_ENV}" -eq 1 || \
      "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Updating packages in panoptes-env."
  conda update -n panoptes-env --quiet --yes conda
  conda update -n panoptes-env --quiet --yes --all
fi

if [[ "${DO_INSTALL_CONDA_PACKAGES}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Installing conda packages needed for PANOPTES"
  conda install --yes "--file=${THIS_DIR}/conda-packages-list.txt"
fi

echo_bar
echo "PATH=$PATH"
echo_bar

exit

if [[ "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Installing Python packages using pip"
  # Upgrade pip itself before installing other python packages.
  pip install -U pip
  pip install -r "${POCS}/requirements.txt"
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


cd "${PANDIR}"
rmdir --ignore-fail-on-non-empty "${PANDIR}/tmp"

set +x
echo
echo_bar
echo_bar
echo "
Your ${THE_PROFILE} has been modified. To pickup that change,
please logout completely, then log back in. Don't just open
a new terminal window.
"

exit

