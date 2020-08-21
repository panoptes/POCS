Docker Images
=============

POCS is available as a docker image hosted on Google Cloud Registry (GCR):

Image name: `gcr.io/panoptes-exp/panoptes-pocs:latest`

### `develop` image

To build the images locally:

```bash
scripts/setup-local-environment.sh
```

This will build all required images locally and is suitable for testing and development.

Then, to run the test suite locally:

```bash
scripts/testing/test-software.sh
````

### `developer` image

The `developer` image is meant to be be used by developers or anyone wishing to
explore the code. It is the same as the local `develop`, but also installs additional
plotting libraries and the `jupyter` environment.

The image should be built locally using the `docker/setup-local-environment.sh`
script (see above).

The `bin/panoptes-develop up` can then be used to start a docker container
instance that will launch `jupyter lab` from `$PANDIR` automatically.

```bash
bin/panoptes-develop up
```
