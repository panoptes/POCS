#!/bin/bash -e

THIS_DIR="$(dirname "$(readlink -f "${0}")")"

source "${THIS_DIR}/install-functions.sh"

# Install all of the packages specified in the apt-packages-list file.
function install_apt_packages() {
  echo
  echo_running_sudo "apt-get update"
  echo
  my_sudo apt-get update
  # Remove all the comments from the package list and install the packages whose
  # names are left.
  APT_PKGS="$(cut '-d#' -f1 "${THIS_DIR}/apt-packages-list.txt" | sort | uniq)"
  echo
  echo_running_sudo "apt-get install"
  echo
  my_sudo apt-get install --yes ${APT_PKGS}
}

install_apt_packages