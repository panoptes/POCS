# Licensed under a MIT license - see LICENSE.txt
"""
Panoptes Observatory Control System (POCS) is a library for controlling a
PANOPTES hardware unit. POCS provides complete automation of all observing
processes and is inteded to be run in an automated fashion.
"""

from __future__ import absolute_import

import os
import sys

from .utils.config import load_config
from .utils.logger import get_root_logger
from warnings import warn

try:
    from .version import version as __version__
except ImportError:
    __version__ = ''

##################################################################################################
# Private Methods
##################################################################################################


def _check_environment():
    """ Checks to see if environment is set up correctly

    There are a number of environmental variables that are expected
    to be set in order for PANOPTES to work correctly. This method just
    sanity checks our environment and shuts down otherwise.

        POCS    Base directory for PANOPTES
    """
    if sys.version_info[:2] < (3, 0):
        warn("POCS requires Python 3.x to run")

    pandir = os.getenv('PANDIR')
    pocs = os.getenv('POCS')
    if pocs is None:
        sys.exit('Please make sure $POCS environment variable is set')

    if not os.path.exists(pocs):
        sys.exit("$POCS dir does not exist or is empty: {}".format(pocs))

    if not os.path.exists("{}/logs".format(pandir)):
        print("Creating log dir at {}/logs".format(pandir))
        os.makedirs("{}/logs".format(pandir))


def _check_config(temp_config):
    """ Checks the config file for mandatory items """

    if 'directories' not in temp_config:
        sys.exit('directories must be specified in config')

    if 'mount' not in temp_config:
        sys.exit('Mount must be specified in config')

    if 'state_machine' not in temp_config:
        sys.exit('State Table must be specified in config')

    return temp_config

_check_environment()

# Config
_config = _check_config(load_config())

# Logger
_logger = get_root_logger()

from .core import POCS
