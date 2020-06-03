#!/bin/bash -e

POCS=${POCS:-/var/panoptes/POCS}
TAG="${1:-develop}"

cd "${POCS}"

echo "Building local panoptes-pocs:latest"
docker build \
    --quiet \
    -t "panoptes-pocs:latest" \
    -f "${POCS}/docker/latest.Dockerfile" \
    "${POCS}"

echo "Building local panoptes-pocs:develop"

# In the local develop we need to pass git to the docker build context.
sed -i s'/^\.git$/\!\.git/' .dockerignore

docker build \
    --quiet \
    --build-arg IMAGE_URL="panoptes-pocs:latest" \
    -t "panoptes-pocs:develop" \
    -f "${POCS}/docker/develop.Dockerfile" \
    "${POCS}"

# Revert our .dockerignore changes.
sed -i s'/^!\.git$/\.git/' .dockerignore

echo "Done building local images"
