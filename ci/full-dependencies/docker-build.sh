#!/bin/bash -ex

# Build this docker image. If running multiple times, you can speed things
# up by running an apt caching proxy:
#
#       $POCS/scripts/install/run-apt-cache-ng-in-docker.sh
#       APT_PROXY_PORT=3142 $POCS/ci/full-dependencies/docker-build.sh

timestamp="$(date "+%Y%m%d.%H%M%S")"
temp_dir=$(mktemp --directory /tmp/docker-build.${timestamp}.XXXX)
function clean_temp_dir {
  rm -rf "${temp_dir}"
}
trap clean_temp_dir EXIT

echo "Creating docker build context in ${temp_dir}"

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
cp -t "${temp_dir}" \
  "${POCS}"/requirements.txt \
  "${THIS_DIR}"/run_* \
  "${POCS}"/scripts/install/*

echo "Building docker image"

docker build \
  --build-arg apt_proxy_port=$APT_PROXY_PORT \
  --tag "panoptes/full-dependencies" \
  --file $POCS/ci/full-dependencies/Dockerfile -- "${temp_dir}"
