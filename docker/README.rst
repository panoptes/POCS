Docker Images
=============

POCS is available as a docker image hosted on Google Cloud Registry (GCR):

Image name: ``gcr.io/panoptes-exp/panoptes-pocs``

Tags: ``latest``, ``develop``, and ``developer-env``.

Setup
~~~~~

To build the images locally:

.. code:: bash

    docker/setup-local-environment.sh

To run the test suite locally:

.. code:: bash

    scripts/testing/test-software.sh

This will build all three images locally and is suitable for testing and development.

Description
~~~~~~~~~~~

The ``panoptes-pocs`` image comes in three separate flavors, or tags,
that serve different purposes.

latest
^^^^^^

The ``latest`` image is the "production" version of ``panoptes-pocs``.

PANOPTES units should be running this flavor.

When running the install script, this will be the default install option unless the "developer" is selected.

develop
^^^^^^^

The ``develop`` image is used for running the automated tests. These are
run automatically on both GitHub and Travis for all code pushes but can
also be run locally while doing development.

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

