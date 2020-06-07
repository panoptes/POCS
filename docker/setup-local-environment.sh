#!/bin/bash -e

PANDIR=${PANDIR:-/var/panoptes}
POCS=${POCS:-/var/panoptes/POCS}
TAG="${1:-develop}"

# Build panoptes-utils first.
. "${PANDIR}/panoptes-utils/docker/setup-local-environment.sh"

cd "${POCS}"
echo "Building local panoptes-pocs:latest"
docker build \
    --quiet --force-rm \
    --build-arg IMAGE_URL="panoptes-utils:latest" \
    -t "panoptes-pocs:latest" \
    -f "${POCS}/docker/latest.Dockerfile" \
    "${POCS}"

# In the local develop we need to pass git to the docker build context.
sed -i s'/^\.git$/\!\.git/' .dockerignore

echo "Building local panoptes-pocs:develop"
docker build \
    --quiet --force-rm \
    --build-arg IMAGE_URL="panoptes-pocs:latest" \
    -t "panoptes-pocs:develop" \
    -f "${POCS}/docker/develop.Dockerfile" \
    "${POCS}"

echo "Building local panoptes-pocs:developer-env"
docker build \
    --quiet --force-rm \
    --build-arg IMAGE_URL="panoptes-pocs:develop" \
    -t "panoptes-pocs:developer-env" \
    -f "${POCS}/docker/developer-env.Dockerfile" \
    "${POCS}"

# Revert our .dockerignore changes.
sed -i s'/^!\.git$/\.git/' .dockerignore

cat <<EOF
Done building the local images.  To run the development environment enter:

cd $POCS
bin/panoptes-develop up

To run the tests enter:

scripts/testing/test-software.sh
EOF