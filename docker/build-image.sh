#!/usr/bin/env bash
set -e

TAG="${1:-latest}"

IMAGE_NAME="panoptes-pocs"
CLOUD_FILE="cloudbuild.yaml"
SOURCE_DIR="${PANDIR}/POCS"

cd "${SOURCE_DIR}"

echo "Building gcr.io/panoptes-exp/${IMAGE_NAME}:${TAG} in ${SOURCE_DIR}"
gcloud builds submit \
  --substitutions="_TAG=${TAG}" \
  --config "${SOURCE_DIR}/docker/${CLOUD_FILE}" \
  "${SOURCE_DIR}"
