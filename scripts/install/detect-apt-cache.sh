#!/bin/bash -ex

# Tell apt where to find the cache for packages, if one has been setup.

# See:
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

