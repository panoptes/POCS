#!/bin/bash -ex

# Build this docker image. If running multiple times, you can speed things
# up by running an apt caching proxy:
#
#       $POCS/scripts/install/run-apt-cache-ng-in-docker.sh
#       APT_PROXY_PORT=3142 ./docker-build.sh

THIS_DIR="$(dirname "$(readlink -f "${0}")")"

# To make it easier to copy this file into multiple
# directories, we generate the image name (tag) from
# the name of the leaf directory.
THIS_LEAF_DIR="$(basename "${THIS_DIR}")"
TAG="panoptes/${THIS_LEAF_DIR}"

timestamp="$(date "+%Y%m%d.%H%M%S")"
temp_dir=$(mktemp --tmpdir --directory docker-build.${THIS_LEAF_DIR}.${timestamp}.XXXX)
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

echo "Building docker image: ${TAG}"

docker build \
  --build-arg apt_proxy_port=$APT_PROXY_PORT \
  --tag "${TAG}" \
  --file "${THIS_DIR}"/Dockerfile -- "${temp_dir}"
