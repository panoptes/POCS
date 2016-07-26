# Licensed under a MIT license - see LICENSE.txt
"""
Panoptes Observatory Control System (POCS) is a library for controlling a
PANOPTES hardware unit. POCS provides complete automation of all observing
processes and is inteded to be run in an automated fashion.
"""

from __future__ import absolute_import

import os
import sys

from .core import POCS
from .utils.config import load_config
from .utils.logger import get_root_logger
from warnings import warn

if sys.version_info[:2] < (3, 0):
    warn("POCS requires Python 3.x to run")

try:
    from .version import version as __version__
except ImportError:
    # TODO: Issue a warning using the logging framework
    __version__ = ''
try:
    from .version import githash as __githash__
except ImportError:
    # TODO: Issue a warning using the logging framework
    __githash__ = ''

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
    pocs = os.getenv('POCS')
    if pocs is None:
        sys.exit('Please make sure $POCS environment variable is set')


def _check_config(temp_config):
    """ Checks the config file for mandatory items """

    if 'directories' not in temp_config:
        warn('directories must be specified in config_local.yaml')

    if 'mount' not in temp_config:
        warn('Mount must be specified in config')

    if 'state_machine' not in temp_config:
        warn('State Table must be specified in config')

    return temp_config

_check_environment()

# Config
_config = _check_config(load_config())

# Logger
_logger = get_root_logger()
