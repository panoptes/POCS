#!/bin/bash -e

# Tell apt where to find the cache for packages, if one has been setup.
# We look for the APT_PROXY_PORT environment variable to be set to the port
# number, else for the first argument to be set to the port number.

# Requires root access in order to write to /etc/apt/apt.conf.d/01proxy

# TODO(james): Determine if we can replace this change of the config file
# with a --option flag on apt-get, ala:
#
#   apt-get -o "Acquire::HTTP::Proxy=${APT_PROXY_URL}" install ...
#
# This would avoid the need for sudo outside of docker build, and would
# avoid docker build permanently recording the proxy in docker image.

# To learn more, see:
# https://github.com/sameersbn/docker-apt-cacher-ng
# https://gist.github.com/dergachev/8441335
# https://chandrusoft.wordpress.com/2012/09/30/disable-proxy-when-using-apt-get/

APT_PROXY_PORT="${APT_PROXY_PORT:-${1}}"
if [ -z "${APT_PROXY_PORT}" ] ; then
  echo "No apt cache proxy declared via APT_PROXY_PORT or script argument."
  exit 0
fi
echo "APT_PROXY_PORT: ${APT_PROXY_PORT}"

# Need to figure out our IP address. We'll try multiple techniques.
HOST_IP=$(awk '/^[a-z]+[0-9]+\t00000000/ { printf("%d.%d.%d.%d\n", "0x" substr($3, 7, 2), "0x" substr($3, 5, 2), "0x" substr($3, 3, 2), "0x" substr($3, 1, 2)) }' < /proc/net/route)
if [ -z "${HOST_IP}" -a -x /sbin/ip ] ; then
  HOST_IP=$(/sbin/ip route get 8.8.8.8 | awk -F"src " 'NR==1{split($2,a," ");print a[1]}')
fi
if [ -z "${HOST_IP}" ] ; then
  echo "Unable to determine host IP address!"
  exit 1
fi

APT_PROXY_URL="http://${HOST_IP}:${APT_PROXY_PORT}"
APT_PROXY_FILE=/etc/apt/apt.conf.d/01proxy

if [ 0 == $(id -u) ]; then
  # Running as root already.
  cat >> "${APT_PROXY_FILE}" <<EOL
Acquire::HTTP::Proxy "${APT_PROXY_URL}";
Acquire::HTTPS::Proxy "false";
EOL
else
  echo "Running sudo to write to ${APT_PROXY_FILE}; you may be prompted for"
  echo "your password..."
  (set -x ; cat <<EOL | sudo tee --append "${APT_PROXY_FILE}" > /dev/null
Acquire::HTTP::Proxy "${APT_PROXY_URL}";
Acquire::HTTPS::Proxy "false";
EOL
)
fi

cat /etc/apt/apt.conf.d/01proxy
echo
echo "Using apt proxy at: ${APT_PROXY_URL}"
