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
##  Target Class
##----------------------------------------------------------------------------
@logger.has_logger
class Target(object):
    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """
    def __init__(self, dict):
        """Takes in a dictionary describing the target as read from the YAML
        file.  Populates the target properties from that dictionary.
        """
        ## name
        self.config = load_config()

        assert 'name' in dict.keys()
        assert isinstance(dict['name'], str)
        self.name = dict['name']
        ## priority
        try:
            self.priority = float(dict['priority'])
        except:
            self.priority = 1.0
        ## position
        try:
            self.position = SkyCoord(dict['position'], dict['frame'])
        except:
            self.position = None
        ## equinox (assumes J2000 if unspecified)
        try:
            self.position.equinox = dict['equinox']
        except:
            self.position.equinox = 'J2000'
        ## equinox (assumes 2000 if unspecified)
        try:
            self.position.obstime = float(dict['epoch'])
        except:
            self.position.obstime = 2000.
        ## proper motion (is tuple of dRA/dt dDec/dt)
        try:
            self.proper_motion = (dict['proper_motion'].split()[0], dict['proper_motion'].split()[1])
        except:
            self.proper_motion = (0.0, 0.0)
        ## visit
        self.visit = []
        obs_list = dict['visit']
        for obs_dict in obs_list:
            self.visit.append(Observation(obs_dict))


    def estimate_visit_duration(self, overhead=0*u.s):
        """Method to estimate the duration of a visit to the target.

        A quick and dirty estimation of the time it takes to execute the
        visit.  Does not currently account for overheads such as readout time,
        slew time, or download time.

        This function just sums over the time estimates of the observations
        which make up the visit.

        Args:
            overhead (astropy.units.Quantity): The overhead time for the visit in
            units which are reducible to seconds.  This is the overhead which occurs
            for each observation.

        Returns:
            astropy.units.Quantity: The duration (with units of seconds).
        """
        duration = 0*u.s
        for obs in self.visit:
            duration += obs.estimate_duration() + overhead
        self.logger.debug('Visit duration estimated as {}'.format(duration))
        return duration
