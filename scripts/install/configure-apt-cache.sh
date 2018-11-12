#!/bin/bash -e

# Tell apt where to find the local (on-host) caching proxy for APT packages,
# if one has been setup. Pass in the port as the first (and only) argument
# to this script, else set the APT_PROXY_PORT environment variable to the
# port number. Records the URL of the proxy "permanently" in
# /etc/apt/apt.conf.d/01proxy; root access is required to write to
# that file.
#
# Using this script is appropriate if it isn't practical to pass the
# URL of the proxy on the apt-get command line, such as this way:
#
#   apt-get -o "Acquire::HTTP::Proxy=${APT_PROXY_URL}" install ...
#
# The script install-apt-packages.sh uses this latter approach.
#
# To learn more, see:
# https://github.com/sameersbn/docker-apt-cacher-ng
# https://gist.github.com/dergachev/8441335
# https://chandrusoft.wordpress.com/2012/09/30/disable-proxy-when-using-apt-get/

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
# shellcheck source=/var/panoptes/POCS/scripts/install/install-helper-functions.sh
source "${THIS_DIR}/install-helper-functions.sh"

# shellcheck disable=SC2086
APT_PROXY_URL="$(get_apt_proxy_url ${1})"
if [ -z "${APT_PROXY_URL}" ] ; then
  echo "Unable to find operating APT proxy!" 1>&2
  exit 1
fi

APT_PROXY_FILE=/etc/apt/apt.conf.d/01proxy

if [ 0 == "$(id -u)" ]; then
  # Running as root already.
  cat >> "${APT_PROXY_FILE}" <<EOL
Acquire::HTTP::Proxy "${APT_PROXY_URL}";
Acquire::HTTPS::Proxy "false";
EOL
else
  echo "Running sudo to append to ${APT_PROXY_FILE}; you may be prompted for"
  echo "your password..."
  (set -x ; cat <<EOL | sudo tee --append "${APT_PROXY_FILE}" > /dev/null
Acquire::HTTP::Proxy "${APT_PROXY_URL}";
Acquire::HTTPS::Proxy "false";
EOL
)
fi

echo
echo "Appended to ${APT_PROXY_FILE}"
echo_bar
cat /etc/apt/apt.conf.d/01proxy
echo_bar
echo
echo "Using apt proxy at: ${APT_PROXY_URL}"
