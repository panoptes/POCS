#!/usr/bin/env bash
set -e

INCLUDE_UTILS=${INCLUDE_UTILS:-false}
INCLUDE_DEVELOPER=${INCLUDE_DEVELOPER:-false}

TAG="${TAG:-develop}"

PANDIR="${PANDIR:-${PWD}/../}"
PANOPTES_UTILS=${PANOPTES_UTILS:-${PANDIR}/panoptes-utils}
PANOPTES_POCS=${PANOPTES_POCS:-${PANDIR}/POCS}

UTILS_IMAGE_URL="gcr.io/panoptes-exp/panoptes-utils:${TAG}"

echo "Setting up local environment in ${PANOPTES_POCS}"
cd "${PANOPTES_POCS}"

build_utils() {
  echo "Building panoptes-utils:${TAG} from ${PANOPTES_UTILS}"
  INCLUDE_BASE=true "${PANOPTES_UTILS}/scripts/setup-local-environment.sh"
  # Use our local image for build below instead of gcr.io image.
  UTILS_IMAGE_URL="panoptes-utils:${TAG}"
  echo "Setting UTILS_IMAGE_URL=${UTILS_IMAGE_URL}"
}

build_develop() {
  echo "Building local panoptes-pocs:${TAG} from ${UTILS_IMAGE_URL} in ${PANOPTES_POCS}"
  docker build \
    --build-arg "image_url=${UTILS_IMAGE_URL}" \
    -t "panoptes-pocs:${TAG}" \
    -f "${PANOPTES_POCS}/docker/Dockerfile" \
    "${PANOPTES_POCS}"
}

build_developer() {
  echo "Building local panoptes-pocs:developer from panoptes-pocs:${TAG} in ${PANOPTES_POCS}"
  docker build \
    --build-arg "userid=$(id -u)" \
    -t "panoptes-pocs:developer" \
    -f "${PANOPTES_POCS}/docker/developer/Dockerfile" \
    "${PANOPTES_POCS}"
}

####################################################################################
# Script logic below
####################################################################################

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
