#!/bin/bash -ex

THIS_DIR="$(dirname "$(readlink -f "${0}")")"

IMAGE_NAME="panoptes/local-image"

echo "Building docker image ${IMAGE_NAME}"

docker build \
  --build-arg user_name=$(id -u -n) \
  --build-arg user_id=$(id -u) \
  --build-arg group_name=$(id -g -n) \
  --build-arg group_id=$(id -g) \
  --tag "${IMAGE_NAME}" \
  --file $THIS_DIR/Dockerfile -- "${THIS_DIR}"
