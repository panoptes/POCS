PANOPTES Observatory Control System
===================================

.. raw:: html

   <p align="center">
   <img src="https://projectpanoptes.org/uploads/2018/12/16/pan-logo.png" alt="PANOPTES logo" />
   </p>

|PyPI version| |Build Status| |codecov| |Documentation Status|

-  `PANOPTES Observatory Control
   System <#panoptes-observatory-control-system>`__
-  `Overview <#overview>`__
-  `Getting Started <#getting-started>`__
-  `Install <#install-script>`__
-  `Test POCS <#test-pocs>`__
-  `Links <#links>`__

Overview
--------

`PANOPTES <https://projectpanoptes.org>`__ is an open source citizen science project
that is designed to find transiting exoplanets with digital cameras. The goal of
PANOPTES is to establish a global network of of robotic cameras run by amateur
astronomers schools in order to monitor, as continuously as possible, a very large
number of stars. For more general information about the project, including the
science case and resources for interested individuals, see the `about page <https://projectpanoptes.org/articles/what-is-panoptes/>`__.

POCS (PANOPTES Observatory Control System) is the main software driver for the
PANOPTES unit, responsible for high-level control of the unit. This repository
also contains a number of scripts for running a full instance of POCS.

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

Install
-------

Coming Soon!  For now see the Testing section of the :ref:`contribute` guide.

Test POCS
---------

See the Testing section of the :ref:`contribute` guide.

Links
-----

-  PANOPTES Homepage: https://projectpanoptes.org
-  PANOPTES Data Explorer: https://www.panoptes-data.org
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
.. |Build Status| image:: https://travis-ci.com/panoptes/pocs.svg?branch=develop
   :target: https://travis-ci.com/panoptes/pocs
.. |codecov| image:: https://codecov.io/gh/panoptes/pocs/branch/develop/graph/badge.svg
   :target: https://codecov.io/gh/panoptes/pocs
.. |Documentation Status| image:: https://readthedocs.org/projects/pocs/badge/?version=latest
   :target: https://pocs.readthedocs.io/en/latest/?badge=latest
