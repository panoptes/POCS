#!/usr/bin/env bash
set -e

INCLUDE_DEVELOPER=${INCLUDE_DEVELOPER:-true}

TAG="${TAG:-develop}"

PANDIR="${PANDIR:-${PWD}/../}"
PANOPTES_POCS=${PANOPTES_POCS:-${PANDIR}/POCS}

UTILS_IMAGE_URL="${UTILS_IMAGE_URL:-panoptes-utils:${TAG}}"

echo "Setting up local environment in ${PANOPTES_POCS}"
cd "${PANOPTES_POCS}"

build_developer() {
  echo "Building local panoptes-pocs:developer from ${UTILS_IMAGE_URL} in ${PANOPTES_POCS}"
  docker build \
    --build-arg "image_url=${UTILS_IMAGE_URL}" \
    -t "panoptes-pocs:developer" \
    -f "${PANOPTES_POCS}/docker/developer/Dockerfile" \
    "${PANOPTES_POCS}"

  # Use the developer version for building local.
  UTILS_IMAGE_URL="panoptes-pocs:developer"
}

build_develop() {
  echo "Building local panoptes-pocs:${TAG} from ${UTILS_IMAGE_URL} in ${PANOPTES_POCS}"
  docker build \
    --build-arg "image_url=${UTILS_IMAGE_URL}" \
    -t "panoptes-pocs:${TAG}" \
    -f "${PANOPTES_POCS}/docker/Dockerfile" \
    "${PANOPTES_POCS}"

}

####################################################################################
# Script logic below
####################################################################################

if [ "${INCLUDE_DEVELOPER}" = true ]; then
  build_developer
fi

build_develop

cat <<EOF
Done building the local images.

To run the tests enter:

scripts/testing/test-software.sh
EOF
