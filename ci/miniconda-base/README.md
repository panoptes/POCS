POCS Miniconda Base Dependencies
================================

This directory has tools for building a docker image with the base
Miniconda installation, i.e. without the panoptes env.

The image name ('tag') varies based on whether the name of the
user that will own the installation. Miniconda/Anaconda are designed
for installation by individual users, rather than system wide; there
are instructions available to work around that, but it is less work
to follow the recommended installation pattern than to work around
issues that arise by ignoring that.

This image only adds those linux packages required to install Miniconda.

## Build the image

Execute this command:

```
./docker-build.sh
```

