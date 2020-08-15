#!/usr/bin/env bash

set -e

INCLUDE_BASE=${INCLUDE_BASE:-true} # INCLUDE_UTILS must be true to work.
INCLUDE_UTILS=${INCLUDE_UTILS:-false}
INCLUDE_DEVELOPER=${INCLUDE_DEVELOPER:-false}

PANOPTES_UTILS=${PANOPTES_UTILS:-$PANDIR/panoptes-utils}
PANOPTES_POCS=${PANOPTES_POCS:-$PANDIR/POCS}
_IMAGE_URL="gcr.io/panoptes-exp/panoptes-utils:latest"

echo "Setting up local environment."
cd "${PANOPTES_POCS}"

build_utils() {
  /bin/bash "${PANOPTES_UTILS}/docker/setup-local-environment.sh"
  # Use our local image for build below.
  _IMAGE_URL="panoptes-utils:develop"
}

build_develop() {
  echo "Building local panoptes-pocs:develop from ${_IMAGE_URL} in ${PANOPTES_POCS}"
  docker build \
    --build-arg="image_url=${_IMAGE_URL}" \
    --build-arg="pip_install=." \
    -t "panoptes-pocs:develop" \
    -f "${PANOPTES_POCS}/docker/Dockerfile" \
    "${PANOPTES_POCS}"
}

build_developer() {
  echo "Building local panoptes-pocs:developer from ${_IMAGE_URL} in ${PANOPTES_POCS}"
  docker build \
    -t "panoptes-pocs:developer" \
    -f "${PANOPTES_POCS}/docker/developer.Dockerfile" \
    "${PANOPTES_POCS}"
}

if [ "${INCLUDE_UTILS}" = true ]; then
  build_utils
fi

build_develop

if [ "${INCLUDE_DEVELOPER}" = true ]; then
  build_developer
fi

cat <<EOF
Done building the local images.

To run the tests enter:

scripts/testing/test-software.sh
EOF
