#!/bin/bash -e

# Run with --help to see your options. With no options, does a complete install
# of dependencies, though attempts to reuse existing installs.

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
THIS_PROGRAM="$(basename "${0}")"


# We try to figure out where things are so that minimal work is required
# by the user.
VARS_ARE_OK=1
GUESSED_A_VAR=0
if [[ -z "${PANDIR}" ]] ; then
  if [[ -d /var/panoptes ]] ; then
    PANDIR=/var/panoptes
    GUESSED_A_VAR=1
  else
    echo "PANDIR variable not set to a directory; usually /var/panoptes."
    VARS_ARE_OK=0
  fi
elif [[ -e "${PANDIR}" && ! -d "${PANDIR}" ]] ; then
  echo "PANDIR (${PANDIR}) is not a directory."
  VARS_ARE_OK=0
fi

if [[ -z "${POCS}" && ! -z "${PANDIR}" ]] ; then
  POCS="${PANDIR}/POCS"
  GUESSED_A_VAR=1
fi
if [[ -z "${POCS}" ]] ; then
  echo "POCS variable not set to a directory; usually /var/panoptes/POCS."
  VARS_ARE_OK=0
elif [[ ! -d "${POCS}" ]] ; then
  echo '$'"POCS (${POCS}) is not a directory."
  VARS_ARE_OK=0
fi

if [[ -z "${PAWS}" && ! -z "${PANDIR}" ]] ; then
  PAWS="${PANDIR}/PAWS"
  GUESSED_A_VAR=1
fi
if [[ -z "${PAWS}" ]] ; then
  echo "PAWS variable not set to a directory; usually /var/panoptes/PAWS."
  VARS_ARE_OK=0
elif [[ ! -d "${PAWS}" ]] ; then
  echo '$'"PAWS (${PAWS}) is not a directory."
  VARS_ARE_OK=0
fi

if [[ -z "${PANLOG}" && ! -z "${PANDIR}" ]] ; then
  PANLOG="${PANDIR}/logs"
  GUESSED_A_VAR=1
fi
if [[ -z "${PANLOG}" ]] ; then
  echo "PANLOG variable not set to a directory; usually /var/panoptes/logs."
  VARS_ARE_OK=0
elif [[ -e "${PANLOG}" && ! -d "${PANLOG}" ]] ; then
  echo '$'"PANLOG (${PANLOG}) is not a directory."
  VARS_ARE_OK=0
fi

if [[ -z "${PANUSER}" && "$(whoami)" == "panoptes" ]] ; then
  PANUSER="panoptes"
  GUESSED_A_VAR=1
elif [[ -z "${PANUSER}" ]] ; then
  echo "Unable to determine the PANOPTES user name (PANUSER); usually panoptes."
  VARS_ARE_OK=0
fi

if [[ "${VARS_ARE_OK}" == "0" ]] ; then
  echo "Please set the Panoptes environment variables, then re-run this script."
  exit 1
fi

if [[ "${GUESSED_A_VAR}" == "1" ]] ; then
  echo "
    Using these variable assignments:

     PANDIR = ${PANDIR}
       POCS = ${POCS}
       PAWS = ${PAWS}
     PANLOG = ${PANLOG}
    PANUSER = ${PANUSER}
"
fi

source "${THIS_DIR}/install-functions.sh"

TIMESTAMP="$(date "+%Y%m%d.%H%M%S")"
INSTALL_LOGS_DIR="${PANDIR}/logs/install/${TIMESTAMP}"
# To which shell file do we need to prepend our additions?
SHELL_RC="${HOME}/.bashrc"
PANOPTES_ENV_SH="${PANDIR}/set-panoptes-env.sh"

# Export these so they can be accessed in install-miniconda.sh and
# other install scripts executed by this one.
export PANDIR POCS PAWS PANLOG PANUSER
export DO_CONDA=1
export DO_REBUILD_CONDA_ENV=0
export DO_INSTALL_CONDA_PACKAGES=1
export DO_PIP_REQUIREMENTS=1

DO_APT_GET=1
DO_MONGODB=1
DO_ASTROMETRY=1
DO_ASTROMETRY_INDICES=1
DO_RUN_ONE_FUNCTION=""

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
--no-conda                 don't install the latest version of Anaconda
--no-conda-packages        don't install packages into Anaconda
--rebuild-conda-env        rebuild the panoptes-env
--no-astrometry            don't install astrometry.net software
--no-astrometry-indices    don't install astrometry.net indices
--no-pip-requirements      don't install python packages
"
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

source "${THIS_DIR}/install-functions.sh"

#-------------------------------------------------------------------------------
# Misc helper functions.

# Backup the file whose path is the first arg, and print the path of the
# backup file. If the file doesn't exist, no path is output.
function backup_file() {
  local -r the_original="${1}"
  if [[ ! -e "${the_original}" ]] ; then
    return
  fi
  if [[ ! -f "${the_original}" ]] ; then
    echo 1>2 "
${the_original} is not a regular file, can't copy!
"
    exit 1
  fi
  local -r the_backup="$(mktemp "${the_original}.backup.XXXXXXX")"
  cp -p "${the_original}" "${the_backup}"
  echo "${the_backup}"
}

function diff_backup_and_file_then_cleanup() {
  local -r the_backup="${1}"
  local -r the_file="${2}"
  if [[ -z "${the_backup}" ]] ; then
    echo_bar
    echo
    echo "Created ${the_file}:"
    echo
    cat "${the_file}"
    echo
    return
  fi
  if ! cmp "${the_backup}" "${the_file}" ; then
    echo_bar
    echo
    echo "Modified ${the_file}:"
    echo
    diff -u "${the_backup}" "${the_file}" || /bin/true
    echo
  fi
  rm -f "${the_backup}"
}

#-------------------------------------------------------------------------------
# Functions for creating the file in which we record the PANOPTES environment
# variables and shell setup commands, and for inserting a 'source <the file>'
# into the rc file of the user's shell (e.g. $HOME/.bashrc for bash).

# If the desired shell rc file doesn't exist, create it.
function ensure_shell_rc_exists() {
  if [[ ! -f "${SHELL_RC}" ]] ; then
    touch "${SHELL_RC}"
  fi
}

# Return a status code indicating whether the profile file contains the
# text in the first arg to this function (true if contains, false otherwise).
function profile_contains_text() {
  local -r target_text="${1}"
  if grep -F -q -- "${target_text}" "${SHELL_RC}" ; then
    return 0
  else
    return 1
  fi
}

# Add the text of the first arg to the PANOPTES environment setup.
function add_to_panoptes_env_setup() {
  PANOPTES_ENV_SETUP+=("${1}")
}

# Append $1 to PATH and write command to do the same to the
# PANOPTES environment setup.
function add_to_PATH() {
  local -r the_dir="$(readlink -f "${1}")"
  PATH="${the_dir}:${PATH}"
  PANOPTES_ENV_SETUP+=("PATH=\"${the_dir}:\${PATH}\"")
}

# Create (or overwrite) the PANOPTES environment setup file,
# and print a diff showing the changes, if there are any.
function update_panoptes_env_file() {
  local  -r the_backup="$(backup_file "${PANOPTES_ENV_SH}")"
  cat >"${PANOPTES_ENV_SH}" <<END_OF_FILE
# PANOPTES environment setup.

export PANDIR="${PANDIR}"
export POCS="${POCS}"
export PAWS="${PAWS}"
export PANLOG="${PANLOG}"
export PANUSER="${USER}"

# Configure the conda environment:
. "\${PANDIR}/miniconda/etc/profile.d/conda.sh"
conda activate panoptes-env

# Add astrometry to the path.
PATH="${ASTROMETRY_DIR}/bin:\${PATH}"

END_OF_FILE
  # We allow for other (optional) commands to be added by adding to
  # the array PANOPTES_ENV_SETUP.
  printf '%s\n' "${PANOPTES_ENV_SETUP[@]}" >>"${PANOPTES_ENV_SH}"
  diff_backup_and_file_then_cleanup "${the_backup}" "${PANOPTES_ENV_SH}"
}

# Arrange for the PANOPTES environment setup file to be used
# when the rc file of the user's shell is executed.
function update_shell_rc_file() {
  if [[ ! -f "${SHELL_RC}" ]] ; then
    cat >"${PANOPTES_ENV_SH}" <<END_OF_FILE
# File created by PANOPTES install-dependencies.sh
source ${PANOPTES_ENV_SH}
END_OF_FILE
    echo_bar
    echo
    echo "Created ${SHELL_RC}."
    return
  fi
  local -r new_text="source ${PANOPTES_ENV_SH}"
  if profile_contains_text "${new_text}" ; then
    # TODO Add logging/verbosity support, so messages like this always
    # go to the log file, and conditionally to stdout or stderr.
    echo "Already in ${SHELL_RC}: ${new_text}"
    return 0
  fi
  local  -r the_backup="$(backup_file "${SHELL_RC}")"
    (cat <<END_OF_FILE; cat "${the_backup}") > "${SHELL_RC}"
# Added by PANOPTES install-dependencies.sh
source ${PANOPTES_ENV_SH}

END_OF_FILE
  diff_backup_and_file_then_cleanup "${the_backup}" "${SHELL_RC}"
}

#-------------------------------------------------------------------------------

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
  "${THIS_DIR}/install-apt-packages.sh"
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
  # lsb_release is deprecated, removed from many debian distributions,
  # and not present in the official Ubuntu docker images. /etc/os-release
  # is recommended instead.
  if [ -f /etc/os-release ] ; then
    LSB_RELEASE="$(grep VERSION_CODENAME= /etc/os-release | cut -d= -f2)"
  elif [[ -n "$(safe_which lsb_release)" ]] ; then
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
  my_sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv ${MONGO_KEY}
  echo "deb ${MONGO_URL} multiverse" | my_sudo tee "${MONGO_SOURCE_PATH}"
  echo "
Updating the list of packages so APT finds the MongoDB packages,
then installing MongoDB.
"
  my_sudo apt-get update
  my_sudo apt-get install -y mongodb-org
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
WantedBy=multi-user.target" | my_sudo tee /lib/systemd/system/mongod.service

  my_sudo systemctl daemon-reload
  my_sudo systemctl start mongod
  my_sudo systemctl enable mongod
}

function maybe_install_mongodb() {
  if [[ -z "$(safe_which mongo)" ]] || ! (systemctl | grep -q -F mongo) ; then
    install_mongodb
  fi
}

function get_installed_astrometry_version() {
  local -r solve_field="${ASTROMETRY_DIR}/bin/solve-field"
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
# then builds and installs into ${ASTROMETRY_DIR}. Skips as much as
# possible if able to determine that the version hasn't changed.
function install_astrometry() {
  ASTROMETRY_VERSION="${ASTROMETRY_VERSION}" "${THIS_DIR}/install-astrometry.sh"
  return



  local -r FN="astrometry.net-${ASTROMETRY_VERSION}.tar.gz"
  local -r URL="http://astrometry.net/downloads/${FN}"
  local -r SCRATCH_DIR="$(mktemp -d "${PANDIR}/tmp/install-astrometry.XXXXXXXXXXXX")"
  local -r INSTALL_TO="${ASTROMETRY_DIR}"
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
  mkdir -p "${ASTROMETRY_DIR}/data"
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

# Install Mongodb, a document database. Used by POCS for storing observation
# metadata and the environment readings from which weather plots are generated.
if [[ "${DO_MONGODB}" -eq 1 ]] ; then
  maybe_install_mongodb
fi

# Install the astrometry.net software package, enabling plate-solving
# of images captured by a PANOPTES unit.
if [[ "${DO_ASTROMETRY}" -eq 1 ]] ; then
  (maybe_install_astrometry)
fi
if [[ "${DO_ASTROMETRY_INDICES}" -eq 1 ]] ; then
  (install_astrometry_indices)
fi

update_panoptes_env_file
update_shell_rc_file

# Cleanup the tmp directory, but only if it is empty.
rmdir --ignore-fail-on-non-empty "${PANDIR}/tmp"

set +x

echo
echo_bar
echo_bar
echo
echo "
Installation complete. Please run these commands:
      source ${PANOPTES_ENV_SH}
      cd \$POCS
      python setup.py install ; pytest
None of the tests should fail.
"

exit
