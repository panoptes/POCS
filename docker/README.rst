Docker Images
=============

POCS is available as a docker image hosted on Google Cloud Registry (GCR):

Image name: ``gcr.io/panoptes-exp/panoptes-pocs``

Setup
~~~~~

To build the images locally:

.. code:: bash

    INCLUDE_UTILS=true docker/setup-local-environment.sh

Then, to run the test suite locally:

.. code:: bash

    panoptes-develop test

This will build all required images locally and is suitable for testing and development.

developer-env
^^^^^^^^^^^^^

The ``developer-env`` image is meant to be be used by developers or anyone wishing to
explore the code. The image should be built locally using the ``docker/setup-local-environment.sh``
script (or, ideally, just use the ``install-pocs`` script).

The ``bin/panoptes-develop up`` can then be used to start a docker container
instance that will launch ``jupyter-lab`` from ``$PANDIR`` automatically.

There are a few ways to get the development version.

1) If you have ``git`` and are comfortable using the command line:

.. code-block:: bash

    cd $PANDIR

    # Get the repository.
    git clone https://github.com/panoptes/panoptes-pocs.git
    cd panoptes-pocs

    # Run environment. 
    bin/panoptes-develop up

2) If you would like to build your own local docker image:

.. code-block:: bash

    cd $PANDIR/panoptes-pocs
    # First build the 'latest' image locally.
    docker build -t panoptes-pocs:latest -f docker/latest.Dockerfile .

    # Then build the develop image locally.
    docker build \
      --build-arg base_image=panoptes-pocs:latest \
      -t panoptes-pocs:develop \
      -f docker/develop.Dockerfile .

    # Wait for build to finish...

    # Run with new image.
    IMAGE=panoptes-pocs bin/panoptes-develop up

3) If you are using a new system:

    TODO: Document this section.

