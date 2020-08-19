#!/usr/bin/env bash
set -e

TAG="${1:-latest}"
IMAGE_NAME="panoptes-pocs"

REPO_NAME="$(git remote get-url origin | cut -d':' -f2)"
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
GITHUB_URL="${2:-https://github.com/${REPO_NAME}}"

CLOUD_FILE="cloudbuild.yaml"
SOURCE_DIR="${PANDIR}/POCS"

cd "${SOURCE_DIR}"

echo "Building   : gcr.io/panoptes-exp/${IMAGE_NAME}:${TAG}"
echo "Source dir : ${SOURCE_DIR}"
echo "Github url : ${GITHUB_URL}"
echo "Branch name: ${BRANCH_NAME}"

gcloud builds submit \
  --substitutions="_TAG=${TAG},_GITHUB_URL=${GITHUB_URL},BRANCH_NAME=${BRANCH_NAME}" \
  --config "${SOURCE_DIR}/docker/${CLOUD_FILE}" \
  "${SOURCE_DIR}"
