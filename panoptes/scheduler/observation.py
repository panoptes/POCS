import datetime
import yaml
import types
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.utils import find_current_module
import ephem

import panoptes

from .utils import logger as logger
from .utils.config import load_config

##----------------------------------------------------------------------------
##  Observation Class
##----------------------------------------------------------------------------
@logger.has_logger
class Observation(object):
    def __init__(self, dict):
        """An object which describes a single observation.

        Args:
            dict (dictionary): a dictionary describing the observation as read from
            the YAML file.
        """
        self.config = load_config()
        ## master_exptime (assumes units of seconds, defaults to 120 seconds)
        try:
            self.master_exptime = dict['master_exptime'] * u.s
        except:
            self.master_exptime = 120 * u.s
        ## master_nexp (defaults to 1)
        try:
            self.master_nexp = int(dict['master_nexp'])
        except:
            self.master_nexp = 1
        ## master_filter
        try:
            self.master_filter = int(dict['master_filter'])
        except:
            self.master_filter = None
        ## analyze (defaults to False)
        try:
            self.analyze = dict['master_filter'] in ['True', 'true', 'Yes', 'yes', 'Y', 'y', 'T', 't']
        except:
            self.analyze = False

        ## slave_exptime (assumes units of seconds, defaults to 120 seconds)
        try:
            self.slave_exptime = dict['slave_exptime'] * u.s
        except:
            self.slave_exptime = 120 * u.s
        ## slave_nexp (defaults to 1)
        try:
            self.slave_nexp = int(dict['slave_nexp'])
        except:
            self.slave_nexp = 1
        ## slave_filter
        try:
            self.slave_filter = int(dict['slave_filter'])
        except:
            self.slave_filter = None


    def estimate_duration(self, overhead=0*u.s):
        """Method to estimate the duration of a ingle observation.

        A quick and dirty estimation of the time it takes to execute the
        observation.   Does not take overheads such as slewing, image readout,
        or image download in to consideration.

        Args:
            overhead (astropy.units.Quantity): The overhead time for the observation in
            units which are reducible to seconds.  This is the overhead which occurs
            for each exposure.

        Returns:
            astropy.units.Quantity: The duration (with units of seconds).
        """
        duration = max([(self.master_exptime + overhead)*self.master_nexp,\
                        (self.slave_exptime + overhead)*self.slave_nexp])
        self.logger.debug('Observation duration estimated as {}'.format(duration))
        return duration
