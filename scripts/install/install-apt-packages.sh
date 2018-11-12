#!/bin/bash -ex

# Installs APT packages (e.g. debian/ubuntu packages installed for all users).
# Requires being logged in as root or the ability to successfully execute sudo.

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
# shellcheck source=/var/panoptes/POCS/scripts/install/install-helper-functions.sh
source "${THIS_DIR}/install-helper-functions.sh"

# Suppress prompting for input during package processing, unless DEBIAN_FRONTEND
# is already set. The tzdata package prompts the user to pick a timezone,
# annoying when you're trying to automate things and don't care which time
# zone is selected (the default is UTC).
if [ -z "${DEBIAN_FRONTEND}" ] ; then
  export DEBIAN_FRONTEND=noninteractive
fi

# Generate the basic apt-get install command, minus the list of packages.
# We store into a shell array, i.e. an array of strings.
declare -a apt_get_install=(apt-get install --no-install-recommends --yes)
# shellcheck disable=SC2119
apt_proxy_url="$(get_apt_proxy_url)"
if [ -n "${apt_proxy_url}" ] ; then
  apt_get_install+=(-o "Acquire::HTTP::Proxy=${apt_proxy_url}")
fi

# Install all of the packages specified in the files in the args.
function install_apt_packages() {
  echo
  echo_running_sudo "apt-get update"
  echo
  my_sudo apt-get update

  for APT_PKGS_FILE in "$@"
  do
    # Remove all the comments from the package list and install the packages whose
    # names are left.
    APT_PKGS="$(cut '-d#' -f1 "${APT_PKGS_FILE}" | sort | uniq)"
    echo
    echo_running_sudo "apt-get install for the files in ${APT_PKGS_FILE}"
    echo
    # A note on syntax: ${array_variable} expands to just the first element
    # of the array. ${array_variable[@]} expands to all of the elements.
    # Putting quotes around that has the affect of expanding the array as
    # one quoted string PER element in the array, and thus spaces in
    # a single element (e.g. "a b") doesn't result in multiple 'words'.
    # shellcheck disable=SC2086
    my_sudo "${apt_get_install[@]}" ${APT_PKGS}
  done
}

cd "${THIS_DIR}"

if [ $# -eq 0 ] ; then
  install_apt_packages apt-packages-list.txt
else  
  install_apt_packages "$@"
fi
