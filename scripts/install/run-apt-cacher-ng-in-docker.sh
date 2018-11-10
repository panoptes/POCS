#!/bin/bash -e

# Runs apt-cacher-ng in a docker container, exposing port 3142 which may
# be used by apt. See configure-apt-cache.sh for the consumer portion
# (intended to run inside of containers).

# Note that this caching proxy is limited to caching linux packages,
# and won't cache other items (e.g. miniconda packages). A more general
# caching solution could be useful for PANOPTES application of docker.

CONTAINER_NAME=apt-cacher-ng
CACHE_DIRECTORY="/tmp/$USER-apt-cacher-ng"

# If the container already exists, start it. Exit code is zero (OK) from
# docker start if it restarted a paused container, or if the container is
# already running.
if (docker start "${CONTAINER_NAME}" >/dev/null 2>&1) ; then
  echo "${CONTAINER_NAME} is running."
else
  echo "${CONTAINER_NAME} is not running, so starting it."
  docker run --name "${CONTAINER_NAME}" --init -d --restart=always \
    --publish 3142:3142 \
    --volume "${CACHE_DIRECTORY}:/var/cache/apt-cacher-ng" \
    sameersbn/apt-cacher-ng:3.1-1
fi

if [ -d "${CACHE_DIRECTORY}" ] ; then
  echo "Cache size:" $(du -s -h "${CACHE_DIRECTORY}")
fi
