#!/bin/bash -ex

docker run --name apt-cacher-ng --init -d --restart=always \
  --publish 3142:3142 \
  --volume /tmp/$USER-apt-cacher-ng:/var/cache/apt-cacher-ng \
  sameersbn/apt-cacher-ng:3.1-1
