#!/bin/bash -ex

timestamp="$(date "+%Y%m%d.%H%M%S")"
temp_dir=$(mktemp --directory /tmp/docker-build.${timestamp}.XXXX)
function clean_temp_dir { rm -rf "${temp_dir}" }
trap clean_temp_dir EXIT

echo "Creating docker build context in ${temp_dir}"

cp -t "${temp_dir}" \
  "${POCS}"/requirements.txt \
  "${POCS}"/scripts/install/*

docker build \
  --tag "panoptes/full-dependencies" \
  --file $POCS/ci/full-dependencies/Dockerfile -- "${temp_dir}"
