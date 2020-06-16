PANOPTES Observatory Control System
===================================

|PyPI version| |Build Status| |codecov| |Documentation Status|

-  `PANOPTES Observatory Control
   System <#panoptes-observatory-control-system>`__
-  `Overview <#overview>`__
-  `Getting Started <#getting-started>`__
-  `Install <#install-script>`__
-  `Test POCS <#test-pocs>`__
-  `Links <#links>`__


.. warning::

    The recent `v0.7.0` (May 2020) release of POCS is not backwards compatible. If you
    are one of the folks running that software, please either do a reinstall
    of your system using the instructions below or see our `forum <https://forum.projectpanoptes.org>`__
    for advice.


Overview
--------

Project PANOPTES
^^^^^^^^^^^^^^^^

`PANOPTES <https://www.projectpanoptes.org>`_ is an open source citizen science project
designed to find `transiting exoplanets <https://spaceplace.nasa.gov/transits/en/>`_ with
digital cameras. The goal of PANOPTES is to establish a global network of of robotic
cameras run by amateur astronomers and schools (or anyone!) in order to monitor,
as continuously as possible, a very large number of stars. For more general information
about the project, including the science case and resources for interested individuals, see the
`project overview <https://projectpanoptes.org/articles/>`_.

POCS
^^^^

POCS (PANOPTES Observatory Control System) is the main software driver for a
PANOPTES unit, responsible for high-level control of the unit.

For more information, see the full documentation at: https://pocs.readthedocs.io.

`panoptes-utils <https://www.github.com/panoptes/panoptes-utils>`_ is a related repository and POCS
relies on most of the tools within `panoptes-utils`.  See https://panoptes-pocs.readthedocs.io for
more information.

Getting Started
---------------

POCS is designed to control a fully constructed PANOPTES unit. Additionally,
POCS can be run with simulators when hardware is not present or when the system
is being developed.

For information on building a PANOPTES unit, see the main `PANOPTES <https://projectpanoptes.org>`__ website and join the
`community forum <https://forum.projectpanoptes.org>`__.

To get started with POCS there are three easy steps:

#. **Setup** POCS on the computer you will be using for your unit or for
   development.
#. **Test** your POCS setup by running our testing script
#. **Start using POCS!**

See below for more details.

.. note::

    We rely heavily on much of the code in `panoptes-utils`.

    See https://github.com/panoptes/panoptes-utils

Install
-------

POCS Environment
^^^^^^^^^^^^^^^^

If you are running a PANOPTES unit then you will most likely want the entire
PANOPTES environment.

There is a bash shell script that will attempt to install an entire working POCS
system on your computer.  Some folks even report that it works on a Mac.

To test the script, open a terminal and enter:

.. code-block:: bash

    curl -L https://install.projectpanoptes.org | bash

Or using `wget`:

.. code-block:: bash

    wget -O - https://install.projectpanoptes.org | bash

POCS Module
^^^^^^^^^^^

If you want just the POCS module, for instance if you want to override it in
your own OCS (see `Huntsman-POCS <https://github.com/AstroHuntsman/huntsman-pocs>`_
for an example), then install via `pip`:

.. code-block:: bash

    pip install panoptes-pocs

If you want the extra features, such as Google Cloud Platform connectivity, then
use the extras options:

.. code-block:: bash

    pip install "panoptes-pocs[google]"

Test POCS
---------

See the Testing section of the Contributing guide.

Links
-----

-  PANOPTES Homepage: https://projectpanoptes.org
-  PANOPTES Data Explorer: https://www.panoptes-data.net
-  Community Forum: https://forum.projectpanoptes.org
-  Source Code: https://github.com/panoptes/POCS

.. |Build Status| image:: https://travis-ci.org/panoptes/POCS.svg?branch=develop
    :target: https://travis-ci.org/panoptes/POCS
.. |codecov| image:: https://codecov.io/gh/panoptes/POCS/branch/develop/graph/badge.svg
   :target: https://codecov.io/gh/panoptes/POCS
.. |astropy| image:: http://img.shields.io/badge/powered%20by-AstroPy-orange.svg?style=flat
   :target: http://www.astropy.org/
.. |PyPI version| image:: https://badge.fury.io/py/panoptes-pocs.svg
   :target: https://badge.fury.io/py/panoptes-pocs
.. |Documentation Status| image:: https://readthedocs.org/projects/pocs/badge/?version=latest
   :target: https://pocs.readthedocs.io/en/latest/?badge=latest
