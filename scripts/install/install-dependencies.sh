#!/bin/bash -e

# Run with --help to see your options. With no options, does a complete install
# of dependencies, though attempts to reuse existing installs.

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
THIS_PROGRAM="$(basename "${0}")"

if [[ -z "${PANDIR}" || -z "${POCS}" || -z "${PAWS}" || -z "${PANLOG}" ||
      -z "${PANUSER}" ]] ; then
  echo "Please set the Panoptes environment variables, then re-run this script."
  exit 1
fi

ASTROMETRY_VERSION="latest"
INSTALL_PREFIX="/usr/local"
CONDA_INSTALL_DIR="${PANDIR}/miniconda"
TIMESTAMP="$(date "+%Y%m%d.%H%M%S")"
INSTALL_LOGS_DIR="${PANDIR}/logs/install/${TIMESTAMP}"

DO_APT_GET=1
DO_MONGODB=1
DO_CONDA=1
DO_REBUILD_CONDA_ENV=0
DO_INSTALL_CONDA_PACKAGES=1
DO_CFITSIO=0  # Disabled in favor of installing with apt-get.
DO_ASTROMETRY=1
DO_ASTROMETRY_INDICES=1
DO_PIP_REQUIREMENTS=1
DO_RUN_ONE_FUNCTION=""

# Which bash file do we need to modify? The last found here is the one that
# bash executes for login shells, and so provides the environment for
# all processes under that. THE_PROFILE_TARGET represents the point before
# which we should insert lines.
THE_PROFILE="${HOME}/.profile"
THE_PROFILE_TARGET="# if running bash"
if [[ -f "${HOME}/.bash_login" ]] ; then
  THE_PROFILE="${HOME}/.bash_login"
  THE_PROFILE_TARGET=""
fi
if [[ -f "${HOME}/.bash_profile" ]] ; then
  THE_PROFILE="${HOME}/.bash_profile"
  THE_PROFILE_TARGET=""
fi

# Track the changes that occurred.
PROFILE_HAS_BEEN_CHANGED=0

#-------------------------------------------------------------------------------

function show_help() {
  echo "${THIS_PROGRAM} - Install software needed for PANOPTES.

${THIS_PROGRAM} [options]

options:
-h, --help                 show brief help
-x                         turn on bash debug output
--run <function>           run the named function and exit, for debugging
--no-apt-get               don't run apt-get to install Linux packages
--no-mongodb               don't install and start mongodb server
--no-cfitsio               don't install the latest version of cfitsio
--no-conda                 don't install the latest version of Anaconda
--no-conda-packages        don't install packages into Anaconda
--rebuild-conda-env        rebuild the panoptes-env
--no-astrometry            don't install astrometry.net software
--no-astrometry-indices    don't install astrometry.net indices
--no-pip-requirements      don't install python packages"
}

# Parse the command line args.
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
      DO_RUN_ONE_FUNCTION="${1}"
      shift
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

#-------------------------------------------------------------------------------

# Print a separator bar of # characters.
function echo_bar() {
  local terminal_width
  if [[ -n "$(which resize)" ]] ; then
    terminal_width="$(resize|grep COLUMNS=|cut -d= -f2)"
  elif [[ -n "$(which stty)" ]] ; then
    terminal_width="$(stty size | cut '-d ' -f2)"
  fi
  printf "%${terminal_width:-80}s\n" | tr ' ' '#'
}

# Get the type of the first arg, i.e. shell function, executable, etc.
# For more info: https://ss64.com/bash/type.html
#            or: https://bash.cyberciti.biz/guide/Type_command
function safe_type() {
  type -t "${1}" || /bin/true
}

# Print the disk location of the first arg.
function safe_which() {
  type -p "${1}" || /bin/true
}

# Does the first arg start with the second arg?
function beginswith() { case "${1}" in "${2}"*) true;; *) false;; esac; }

# If the desired profile file doesn't exist, create it.
function ensure_profile_exists() {
  if [[ ! -f "${THE_PROFILE}" ]] ; then
    touch "${THE_PROFILE}"
    PROFILE_HAS_BEEN_CHANGED=1
  fi
}

# Return a status code indicating whether the profile file contains the
# text in the first arg to this function (true if contains, false otherwise).
function profile_contains_text() {
  local -r target_text="${1}"
  if grep -F -q -- "${target_text}" "${THE_PROFILE}" ; then
    return 0
  else
    return 1
  fi
}

# Add the text of the first arg to the profile file, just before the appropriate
# target line, unless the text is already in the file.
function add_to_profile_before_target() {
  local -r new_text="${1}"
  local -r target_text="${2:-${THE_PROFILE_TARGET}}"
  if profile_contains_text "${new_text}" ; then
    # TODO Add logging/verbosity support, so messages like this always
    # go to the log file, and conditionally to stdout or stderr.
    # echo "Already in ${THE_PROFILE}: ${new_text}"
    return 0
  fi
  ensure_profile_exists
  # This backup is just for debugging (i.e. showing the before and after
  # diff).
  local -r the_backup="$(mktemp "${THE_PROFILE}.pre-edit.XXXXX")"
  cp -p "${THE_PROFILE}" "${the_backup}"
  if [[ -n "${target_text}" ]] && \
     profile_contains_text "${target_text}" ; then
    # Add just before the target text.
    # Warning, this isn't a very good sed script. It actually performs
    # the insert before every occurrence of the target text. Sigh.
    sed -i "/${target_text}/i \
# Added by PANOPTES install-dependencies.sh\n\
${new_text}\n" "${THE_PROFILE}"
  else
    # Append to the end of the file.
    echo >>"${THE_PROFILE}" "
# Added by PANOPTES install-dependencies.sh
${new_text}"
  fi
  PROFILE_HAS_BEEN_CHANGED=1
  # Again, this diff is just for debugging.
  echo "Modified ${THE_PROFILE}:"
  echo
  diff -u "${the_backup}" "${THE_PROFILE}" || /bin/true
  echo
  rm "${the_backup}"
}

# Append $1 to PATH and write command to do the same to the profile file.
function add_to_PATH() {
  local -r the_dir="$(readlink -f "${1}")"
  add_to_profile_before_target "PATH=\"${the_dir}:\${PATH}\""
  PATH="${the_dir}:${PATH}"
}

# Given the path to a pkg-config file (.pc), extract the version number.
function extract_version_from_pkg_config() {
  if [[ -f "${1}" ]] ; then
    grep -E '^Version:' "${1}" | cut '-d:' -f2
  else
    echo ""
  fi
}

# Install all of the packages specified in the apt-packages-list file.
function install_apt_packages() {
  echo
  echo "Running sudo apt-get update, you may be prompted for your password."
  echo
  (set -x ; sudo apt-get update)
  # Remove all the comments from the package list and install the packages whose
  # names are left.
  APT_PKGS="$(cut '-d#' -f1 "${THIS_DIR}/apt-packages-list.txt" | sort | uniq)"
  echo
  echo "Running sudo apt-get install, you may be prompted for your password."
  echo
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
  if [[ -n "$(safe_which lsb_release)" ]] ; then
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
  if [[ -z "$(safe_which mongo)" ]] || ! (systemctl | grep -q -F mongo) ; then
    install_mongodb
  fi
}

# Did the user source conda's etc/profile.d/conda.sh?
function conda_is_present() {
  if [[ -z "${CONDA_SHLVL}" ]] ; then
    return 1  # No
  fi
  return 0  # Probably
}

function is_panoptes_env_activated() {
  if ! conda_is_present ; then
    return 1  # No
  fi
  # Do we have a conda executable? If not, then no environment has
  # been activated so far.
  if [[ -z "${CONDA_EXE}" || ! -x "${CONDA_EXE}" ]] ; then
    return 1  # No
  fi
  # Does it work?
  local -r conda_info="$("${CONDA_EXE}" info 2>/dev/null || /bin/true)"
  if [[ -z "${conda_info}" ]] ; then
    return 1  # No
  fi
  # Is the panoptes-env activated?
  if ! (echo "${conda_info}" | grep -q -E 'active environment.*:.*panoptes-env$') ; then
    return 1  # No
  fi
  # Does the env have a valid location?
  local -r env_location="$(echo "${conda_info}" | \
                           (grep -E 'active env location :' || /bin/true) | \
                           cut -d: -f2 | xargs)"
  if [[ -z "${env_location}" ]] ; then
    return 1  # No
  fi
  if [[ ! -d "${env_location}" ]] ; then
    return 1  # No
  fi
  # Is python in that location?
  local -r python_location="$(safe_which python)"
  if ! beginswith "${python_location}" "${env_location}" ; then
    return 1  # No
  fi
  # Looks good.
  return 0
}

# Get the location of the panoptes environment.
function get_panoptes_env_location() {
  if ! conda_is_present ; then
    return
  fi
  # Do we have a conda executable? We don't require CONDA_EXE to already be set
  # because conda doesn't set it  until the first environment is activated.
  local -r conda_exe="${CONDA_EXE:-${CONDA_INSTALL_DIR}/bin/conda}"
  if [[ -z "${conda_exe}" || ! -x "${conda_exe}" ]] ; then
    return  # No
  fi
  # Get the list of environments.
  local -r conda_envs="$("${conda_exe}" info --envs 2>/dev/null || /bin/true)"
  if [[ -z "${conda_envs}" ]] ; then
    return  # Cound't find any environments
  fi
  # Is there a panoptes-env?
  local -r panoptes_env="$(
      echo "${conda_envs}" |
      (grep -E '^panoptes-env[[:space:]]' || /bin/true))"
  if [[ -z "${panoptes_env}" ]] ; then
    return  # No panoptes environment.
  fi
  # Extract the panoptes-env line and print the path that comes at
  # the end of that line.
  echo "${panoptes_env}" | sed 's_.* /_/_'
}

# Checksum the contents of the panoptes env, allowing us to determine
# if it changed. This is useful for upgrades, not the first install.
# For speed and simplicity, we actually just checksum the listing.
function checksum_panoptes_env() {
  local -r location="$(get_panoptes_env_location)"
  if [[ -n "${location}" ]] ; then
    (cd "${location}" ; find . -type f -ls) | md5sum
  fi
}

# Install latest version of Miniconda (Anaconda with very few packages; any that
# are needed can then be installed).
function install_conda() {
  local -r the_destination="${CONDA_INSTALL_DIR}"
  if [[ -d "${the_destination}" ]] ; then
    echo_bar
    echo
    echo "Removing previous miniconda installation from ${the_destination}"
    rm -rf "${the_destination}"
  fi

  echo_bar
  echo
  echo "Installing miniconda. License at: https://conda.io/docs/license.html"
  local -r the_script="${PANDIR}/tmp/miniconda.sh"
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O "${the_script}"
  bash "${the_script}" -b -p "${the_destination}"
  rm "${the_script}"

  # As per the Anaconda 4.4 release notes, one is supposed to add the following
  # to .bash_profile, .bashrc or wherever is appropriate:
  #    . $CONDA_LOCATION/etc/profile.d/conda.sh
  #    conda activate <name-of-desired-environment>
  # Where CONDA_LOCATION is where Anaconda or miniconda was installed.
  # We do the first step here. Later we'll activate the PANOPTES environment.

  add_to_profile_before_target \
      ". ${the_destination}/etc/profile.d/conda.sh"
  . "${the_destination}/etc/profile.d/conda.sh"
}

# Add additional repositories in which conda should search for packages.
function add_conda_channels() {
  # Add the astropy channel, i.e. an additional repository in which to
  # look for packages. With conda 4.1.0 and later, by default the highest
  # priority repository that contains a package is used as the source for
  # that package, even if there is a newer version in a lower priority
  # package. And by default the most recently added repository is treated
  # as the highest priority repository. Here we use prepend to be clear
  # that we want astropy to be highest priority.
  if (conda config --show channels | grep -F -q astropy) ; then
    conda config --remove channels astropy
  fi
  conda config --prepend channels astropy

  # And put conda-forge at the back of the line.
  if (conda config --show channels | grep -F -q conda-forge) ; then
    conda config --remove channels conda-forge
  fi
  conda config --append channels conda-forge
}

# Prepare the conda environment for PANOPTES.
function prepare_panoptes_conda_env() {
  # Use the base Anaconda environment until we're ready to
  # work with the PANOPTES environment.
  conda activate base

  # Determine if the PANOPTES environment already exists.
  local do_create_conda_env=0
  if ! (conda info --envs | grep -q panoptes-env) ; then
    do_create_conda_env=1
  elif [[ "${DO_REBUILD_CONDA_ENV}" -eq 1 ]] ; then
    conda remove --all --yes --quiet -n panoptes-env
    do_create_conda_env=1
  fi

  # Create the PANOPTES environment if necessary.
  if [[ "${do_create_conda_env}" -eq 1 ]] ; then
    echo_bar
    echo
    echo "Creating conda environment 'panoptes-env' with Python 3.6"
    # 3.6 works around a problem building astroscrappy in 3.7.
    conda create -n panoptes-env --yes --quiet python=3.6
  fi

  if [[ "${DO_INSTALL_CONDA_PACKAGES}" -eq 1 ]] ; then
    echo_bar
    echo
    echo "Installing panoptes-env packages."
    conda install -n panoptes-env --yes --quiet "--file=${THIS_DIR}/conda-packages-list.txt"

    echo_bar
    echo
    echo "Updating all panoptes-env packages."
    conda update -n panoptes-env --yes --quiet --all
  fi

  # Activate the PANOPTES environment at login.
  add_to_profile_before_target "conda activate panoptes-env"
}

# Install conda if we can't find it. Note that starting with version
# 4.4, conda's bin directory is not on the path, so 'which conda'
# can't be used to determine if it is present.
function maybe_install_conda() {
  # Just in case conda isn't setup, but exists...
  local -r conda_sh="${CONDA_INSTALL_DIR}/etc/profile.d/conda.sh"
  if [[ -z "$(safe_type conda)" && -f "${conda_sh}" ]] ; then
    . "${conda_sh}"
  fi
  if [[ -z "$(safe_type conda)" ]] ; then
    install_conda
  else
    echo_bar
    echo
    echo "Reusing existing conda installation ($(conda --version)):" "${_CONDA_ROOT}"
  fi
  echo_bar
  echo
  echo "Updating base conda."
  conda update -n base --yes --quiet conda
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

function get_installed_astrometry_version() {
  local -r solve_field="${PANDIR}/astrometry/bin/solve-field"
  if [[ -x "${solve_field}" ]] ; then
    "${solve_field}" --help|(grep -E '^Revision [0-9.]+,' || /bin/true)|cut -c10-|cut -d, -f1
  fi
}

function test_installed_astrometry_version() {
  local -r installed_version="$(get_installed_astrometry_version)"
  if [[ -n "${installed_version}" && \
        "${ASTROMETRY_VERSION}" == "${installed_version}" ]] ; then
    echo_bar
    echo
    echo "Reusing existing astrometry ${installed_version} installation."
    return 0
  else
    return 1
  fi
}

# Downloads astrometry version ${ASTROMETRY_VERSION} into a temp directory,
# then builds and installs into ${PANDIR}/astrometry. Skips as much as
# possible if able to determine that the version hasn't changed.
function install_astrometry() {
  local -r FN="astrometry.net-${ASTROMETRY_VERSION}.tar.gz"
  local -r URL="http://astrometry.net/downloads/${FN}"
  local -r SCRATCH_DIR="$(mktemp -d "${PANDIR}/tmp/install-astrometry.XXXXXXXXXXXX")"
  local -r INSTALL_TO="${PANDIR}/astrometry"
  local -r md5sum_file="${INSTALL_TO}/TAR_MD5SUM.txt"
  local -r make_log="${INSTALL_LOGS_DIR}/make-astrometry.log"
  local -r make_py_log="${INSTALL_LOGS_DIR}/make-astrometry-py.log"
  local -r make_install_log="${INSTALL_LOGS_DIR}/make-astrometry-install.log"
  cd "${SCRATCH_DIR}"

  echo_bar
  echo
  echo "Fetching astrometry into directory $(pwd)"
  wget "${URL}"

  # Is the file the same as the one used for the current install?
  if [[ -f "${md5sum_file}" ]] && md5sum --check --status "${md5sum_file}" && \
    [[ "$(get_installed_astrometry_version)" != "" ]] ; then
    echo_bar
    echo
    echo -n "Checksum matches already installed astrometry version "
    echo "$(get_installed_astrometry_version), not replacing."
    cd "${PANDIR}"
    rm -rf "${SCRATCH_DIR}"
    return
  fi
  local -r tar_md5sum="$(md5sum "${FN}")"

  echo_bar
  echo
  echo "Unpacking ${FN}."
  tar zxf "${FN}"

  if [[ "${ASTROMETRY_VERSION}" == "latest" ]] ; then
    # We need to know the version that is in the tar file in order to
    # enter that directory.
    ASTROMETRY_VERSION=""
    for version in $(find astrometry.net-* -maxdepth 0 -type d | sed "s/astrometry.net-//")
    do
      if [[ "${ASTROMETRY_VERSION}" == "" ]] ; then
        ASTROMETRY_VERSION="${version}"
      else
        echo_bar
        echo
        echo "ERROR: Found two version number directories in the tar file!"
        find astrometry.net-* -maxdepth 0 -type d
        exit 1
      fi
    done

    if [[ ! -f "${md5sum_file}" ]] ; then
      # We've not yet been able to check if the installed version should
      # be replaced.
      if test_installed_astrometry_version ; then
        return
      fi
    fi
  fi

  echo_bar
  echo
  echo "Building astrometry ${ASTROMETRY_VERSION}, logging to ${make_log}"

  cd "astrometry.net-${ASTROMETRY_VERSION}"
  make >"${make_log}" 2>&1

  echo_bar
  echo
  echo "Building astrometry python support, logging to ${make_py_log}"
  make py >"${make_py_log}" 2>&1

  echo_bar
  echo
  echo "Installing built astrometry into directory ${INSTALL_TO},"
  echo "and logging to ${make_install_log}"
  if [[ -d "${INSTALL_TO}" ]] ; then
    rm -rf "${INSTALL_TO}"
  fi
  mkdir -p "${INSTALL_TO}"
  make install "INSTALL_DIR=${INSTALL_TO}" >"${make_install_log}" 2>&1

  add_to_PATH "${INSTALL_TO}/bin"
  cd "${PANDIR}"
  rm -rf "${SCRATCH_DIR}"

  echo "${tar_md5sum}" >"${md5sum_file}"
  local -r installed_version="$(get_installed_astrometry_version)"
  if [[ "${ASTROMETRY_VERSION}" != "${installed_version}" ]] ; then
    echo
    echo "ERROR: version mismatch after installing astrometry!"
    echo "Expected: ${ASTROMETRY_VERSION}"
    echo "  Actual: ${installed_version}"
    exit 1
  fi
}

# Installs astrometry if missing or if the wrong version.
function maybe_install_astrometry() {
  if ! test_installed_astrometry_version ; then
    install_astrometry
  fi
}

# Run a POCS script for installing the indices used by astrometry
# to solve fields.
function install_astrometry_indices() {
  echo_bar
  echo
  echo "Fetching astrometry and other indices."
  mkdir -p "${PANDIR}/astrometry/data"
  python "${POCS}/pocs/utils/data.py"
}

#-------------------------------------------------------------------------------
# Do what the user asked us to do...

mkdir -p "${PANDIR}"
cd "${PANDIR}"
mkdir -p tmp
mkdir -p "${INSTALL_LOGS_DIR}"

# For testing, run the named function in a sub-shell, then exit.
if [[ -n "${DO_RUN_ONE_FUNCTION}" ]] ; then
  if ("${DO_RUN_ONE_FUNCTION}") ; then
    echo "Function was successful."
  else
    echo "Function failed with status $?"
  fi
  exit
fi

# Install packages using the APT package manager. Works on Debian based systems
# such as Ubuntu.
if [[ "${DO_APT_GET}" -eq 1 ]] ; then
  install_apt_packages
fi

# Install Mongodb, a document database. Used by POCS for storing environment
# readings, from which weather plots are generated.
if [[ "${DO_MONGODB}" -eq 1 ]] ; then
  maybe_install_mongodb
fi

# Before installing conda, checksum the environment so we can easily tell
# if it changed.
orig_panoptes_env_checksum="$(checksum_panoptes_env)"

# Before installing conda, figure out if the calling shell had the correct
# environment setup.
had_activated_panoptes_env=0
if panoptes_env_is_activated ; then
  had_activated_panoptes_env=1
fi

# Install Conda, a Python package manager from Anaconda, Inc. Supports both
# pure Python packages (just as pip does) and packages with non-Python parts
# (e.g. native libraries).
if [[ "${DO_CONDA}" -eq 1 ]] ; then
  maybe_install_conda
fi

if [[ "${DO_CONDA}" -eq 1 || \
      "${DO_REBUILD_CONDA_ENV}" -eq 1 || \
      "${DO_INSTALL_CONDA_PACKAGES}" -eq 1 ]] ; then
  prepare_panoptes_conda_env
fi

if [[ -z "$(safe_type conda)" ]] ; then
  echo_bar
  echo "
Error: conda is not installed, but remaining installation steps make
use of the conda environment for PANOPTES (panoptes-env).
"
  exit 1
fi

# Activate the PANOPTES environment in this shell.
conda activate panoptes-env

# Install pure Python packages using pip; note that we prefer to
# install these with conda if they are available that way, as we
# try to reduce the number of package managers and repositories
# we have to deal with.
if [[ "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Upgrading pip before installing other python packages."
  pip install --quiet --upgrade pip

  echo_bar
  echo
  echo "Installing python packages using pip."
  pip install --quiet --requirement "${POCS}/requirements.txt"
fi

# Install cfitsio, native tools for reading and writing FITS files.
if [[ "${DO_CFITSIO}" -eq 1 ]] ; then
  install_latest_cfitsio
fi

# Install the astrometry.net software package, enabling plate-solving
# of images captured by a PANOPTES unit.
if [[ "${DO_ASTROMETRY}" -eq 1 ]] ; then
  (maybe_install_astrometry)
fi
if [[ "${DO_ASTROMETRY_INDICES}" -eq 1 ]] ; then
  (install_astrometry_indices)
fi

# Cleanup the tmp directory, but only if it is empty.
rmdir --ignore-fail-on-non-empty "${PANDIR}/tmp"

set +x

echo
echo_bar
echo_bar
echo

ok_to_test=1
if [[ "${PROFILE_HAS_BEEN_CHANGED}" -eq 1 ]] ; then
  ok_to_test=0
  tput smso  # Enter standout mode
  echo "Your shell initialization script ($THE_PROFILE) has been modified."
  tput rmso  # Exit standout mode
fi

if [[ "${orig_panoptes_env_checksum}" != "$(checksum_panoptes_env)" ]] ; then
  # FOR DEBUGGING:
  echo "orig_panoptes_env_checksum: ${orig_panoptes_env_checksum}"
  echo "new  panoptes_env_checksum: $(checksum_panoptes_env)"
  ok_to_test=0
  tput smso  # Enter standout mode
  echo "Your Python environment has been modified."
  tput rmso  # Exit standout mode
fi

if [[ "${had_activated_panoptes_env}" -eq 0 ]] ; then
  ok_to_test=0
  tput smso  # Enter standout mode
  echo "The conda panoptes-env was not activated."
  tput rmso  # Exit standout mode
fi

if [[ "${ok_to_test}" -eq 0 ]] ; then
  tput smso  # Enter standout mode
  echo "Please log out and back in again to pickup the changes,
then re-run this script, which should leave you ready for testing.
"
  tput rmso  # Exit standout mode
else
  echo "
Installation complete. Please run these commands:
      cd $POCS
      python setup.py install
      pytest
All of the tests should pass.
"
fi

exit
