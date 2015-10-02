import datetime
import yaml
import types
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.utils import find_current_module

from ..utils import logger as logger
from ..utils.config import load_config

##----------------------------------------------------------------------------
##  Observation Class
##----------------------------------------------------------------------------
@logger.has_logger
class Observation(object):
    def __init__(self, obs_config=dict()):
        """An object which describes a single observation.

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
            the YAML file.

        Example:
              - {analyze: false, master_exptime: 300, master_filter: null, master_nexp: 3, slave_exptime: 300,
                slave_filter: null, slave_nexp: 3}
              - {analyze: false, master_exptime: 120, master_filter: null, master_nexp: 5, slave_exptime: 120,
                slave_filter: null, slave_nexp: 5}


        """
        self.config = load_config()

        ## master_exptime (assumes units of seconds, defaults to 120 seconds)
        self.master_exptime = obs_config.get('master_exptime', 120) * u.s

        ## master_nexp (defaults to 1)
        self.master_nexp = obs_config.get('master_nexp', 1)

        ## master_filter
        self.master_filter = obs_config.get('master_filter',  None)

        ## analyze (defaults to False). Note: this is awkward
        self.analyze = obs_config.get('master_filter', False) in ['True', 'true', 'Yes', 'yes', 'Y', 'y', 'T', 't']

        ## slave_exptime (assumes units of seconds, defaults to 120 seconds)
        self.slave_exptime = obs_config.get('slave_exptime',  120) * u.s

        ## slave_nexp (defaults to 1)
        self.slave_nexp = obs_config.get('slave_nexp',  1)

        ## slave_filter
        self.slave_filter = obs_config.get('slave_filter',  None)



    def estimate_duration(self, overhead=0*u.s):
        """Method to estimate the duration of a single observation.

        A quick and dirty estimation of the time it takes to execute the
        observation.  Does not take overheads such as slewing, image readout,
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
