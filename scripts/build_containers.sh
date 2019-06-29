#!/bin/bash -e
SOURCE_DIR="${POCS}"
CLOUD_FILE="cloudbuild-${1:-all}.yaml"

echo "Using ${CLOUD_FILE}"

gcloud builds submit \
    --timeout="5h" \
    --config "${SOURCE_DIR}/docker/${CLOUD_FILE}" \
    --async \
    "${SOURCE_DIR}"

