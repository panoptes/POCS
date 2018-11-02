#!/bin/bash -e

THIS_DIR="$(dirname "$(readlink -f "${0}")")"

source "${THIS_DIR}/install-functions.sh"

# Install all of the packages specified in the in the args.
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
    my_sudo apt-get install --yes ${APT_PKGS}
  done
}

if [ $# -eq 0 ] ; then
  install_apt_packages "${THIS_DIR}"/apt-packages-list.for-*.txt
else  
  install_apt_packages "$@"
fi

