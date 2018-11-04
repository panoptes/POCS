# This file is to be sourced into another to add helper functions
# and environment variables.

# Python 3.6 works around a problem building astroscrappy in 3.7.
PYTHON_VERSION="3.6"
CONDA_INSTALL_DIR="${PANDIR}/miniconda"
CONDA_SH="${CONDA_INSTALL_DIR}/etc/profile.d/conda.sh"

ASTROMETRY_VERSION="0.76"
ASTROMETRY_DIR="${PANDIR}/astrometry"

#-------------------------------------------------------------------------------
# Logging support (nascent; I want to add more control and a log file).

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

function echo_running_sudo() {
  if [ "$(whoami)" == "root" ] ; then
    echo "Running $1"
  else
    echo "Running sudo $1; you may be prompted for your password."
  fi
}

function my_sudo() {
  if [ "$(whoami)" == "root" ] ; then
    "$@"
  else
    (set -x ; sudo "$@")
  fi
}

#-------------------------------------------------------------------------------
# Misc helper functions.

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

#-------------------------------------------------------------------------------

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

#-------------------------------------------------------------------------------
# Anaconda (miniconda) support.

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
  if [[ -d "${CONDA_INSTALL_DIR}" ]] ; then
    echo_bar
    echo
    echo "Removing previous miniconda installation from ${CONDA_INSTALL_DIR}"
    rm -rf "${CONDA_INSTALL_DIR}"
  fi

  echo_bar
  echo
  echo "Installing miniconda. License at: https://conda.io/docs/license.html"
  local -r the_script="${PANDIR}/tmp/miniconda.sh"
  mkdir -p "$(dirname "${the_script}")"
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O "${the_script}"
  bash "${the_script}" -b -p "${CONDA_INSTALL_DIR}"
  rm "${the_script}"

  # As per the Anaconda 4.4 release notes, one is supposed to add the following
  # to .bash_profile, .bashrc or wherever is appropriate:
  #    . $CONDA_INSTALL_DIR/etc/profile.d/conda.sh
  #    conda activate <name-of-desired-environment>
  # Where CONDA_INSTALL_DIR is where Anaconda or miniconda was installed.
  # We do the first step here. Later we'll activate the PANOPTES environment.

  . "${CONDA_SH}"
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
  . "${CONDA_SH}"
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
  . "${CONDA_SH}"
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
    echo "Creating conda environment 'panoptes-env' with Python ${PYTHON_VERSION}"
    conda create -n panoptes-env --yes --quiet "python=${PYTHON_VERSION}"
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
}

# Install conda if we can't find it. Note that starting with version
# 4.4, conda's bin directory is not on the path, so 'which conda'
# can't be used to determine if it is present.
#
# TODO(jamessynge): Stop allowing for an existing conda to be
# located elsewhere.
function maybe_install_conda() {
  # Just in case conda isn't setup, but exists...
  if [[ -z "$(safe_type conda)" && -f "${CONDA_SH}" ]] ; then
    . "${CONDA_SH}"
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
