#!/bin/bash -ex

# Install dependencies that are very stable.






# https://github.com/sameersbn/docker-apt-cacher-ng
# https://gist.github.com/dergachev/8441335

APT_PROXY_PORT="${APT_PROXY_PORT:-${1}}"
if [ -z "${APT_PROXY_PORT}" ] ; then
  echo "No apt cache proxy declared via APT_PROXY_PORT or script argument."
else
  echo "APT_PROXY_PORT :${APT_PROXY_PORT}"
  HOST_IP=$(awk '/^[a-z]+[0-9]+\t00000000/ { printf("%d.%d.%d.%d\n", "0x" substr($3, 7, 2), "0x" substr($3, 5, 2), "0x" substr($3, 3, 2), "0x" substr($3, 1, 2)) }' < /proc/net/route)
  if [ -z "${HOST_IP}" ] ; then
    echo "Unable to determine host IP address!"
  else
    echo 'Acquire::HTTPS::Proxy "false";' >> /etc/apt/apt.conf.d/01proxy
    cat >> /etc/apt/apt.conf.d/01proxy <<EOL
    Acquire::HTTP::Proxy "http://${HOST_IP}:${APT_PROXY_PORT}";
    Acquire::HTTPS::Proxy "false";
EOL
    cat /etc/apt/apt.conf.d/01proxy
    echo "Using host's apt proxy"
  fi
fi









# Suppress prompting for input during package processing.
export DEBIAN_FRONTEND=noninteractive

# Update the information we know about package versions.
apt-get update --fix-missing

# apt-utils is used later when we install some other packages, so
# reduce the number of error messages from debconf by installing
# this early.
apt-get install --no-install-recommends --yes apt-utils

declare -a PACKAGES=(
  #
  # Time zone and daylight-saving time data
  #
  tzdata
  #
  # Astrometry and cfitsio.
  # Not sure if libcfitsio-dev is directly needed.
  #
  astrometry.net "astrometry-data-*" libcfitsio-bin libcfitsio-dev
  #
  # Not sure if these are needed for testing POCS, or just for running.
  #
  dcraw gphoto2 exiftool
  #
  # Cairo is a graphics library, and matplotlib can use it as a backend
  # for rendering.
  #
  libcairo2-dev
  #
  # Graphviz is used for rendering the state machine of POCS.
  # Not sure if these are needed for testing POCS, or just for running.
  #
  graphviz libgraphviz-dev
  #
  # Improves interaction with pocs_shell (via readline).
  #
  libncurses5-dev
  #
  # Tools needed for installing miniconda.
  #
  ca-certificates wget bzip2
)

apt-get install --no-install-recommends --yes "${PACKAGES[@]}"

# Docker best practices calls for cleaning the apt cache before
# the end of this RUN so that it is not stored in the image.
rm -rf /var/lib/apt/lists/*