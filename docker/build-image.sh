#!/bin/bash -e

SOURCE_DIR="${PANDIR}/pocs"
BASE_CLOUD_FILE="cloudbuild.yaml"
TAG="${1:-develop}"

cd "${SOURCE_DIR}"

echo "Building gcr.io/panoptes-exp/pocs"
gcloud builds submit \
    --timeout="1h" \
    --substitutions="_TAG=${TAG}" \
    --config "${SOURCE_DIR}/docker/${BASE_CLOUD_FILE}" \
    "${SOURCE_DIR}"
