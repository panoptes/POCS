
import astropy.units as u

from ..utils.logger import get_logger
from ..utils.config import load_config

from collections import OrderedDict


class Observation(object):

    def __init__(self, obs_config=dict()):
        """An object which describes a single observation.

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
            the YAML file.

        Example:
              - {analyze: false, primary_exptime: 300, primary_filter: null, primary_nexp: 3, secondary_exptime: 300,
                secondary_filter: null, secondary_nexp: 3}


        """
        self.config = load_config()

        self.logger = get_logger(self)

        # primary_exptime (assumes units of seconds, defaults to 120 seconds)
        self.primary_exptime = obs_config.get('primary_exptime', 120) * u.s

        # primary_nexp (defaults to 1)
        self.primary_nexp = obs_config.get('primary_nexp', 1)
        self.number_exposures = self.primary_nexp

        # primary_filter
        self.primary_filter = obs_config.get('primary_filter', None)

        # analyze (defaults to False). Note: this is awkward
        self.analyze = obs_config.get('primary_filter', False) in ['True', 'true', 'Yes', 'yes', 'Y', 'y', 'T', 't']

        # secondary_exptime (assumes units of seconds, defaults to 120 seconds)
        self.secondary_exptime = obs_config.get('secondary_exptime', 120) * u.s

        # secondary_nexp (defaults to 1)
        self.secondary_nexp = obs_config.get('secondary_nexp', 1)

        # secondary_filter
        self.secondary_filter = obs_config.get('secondary_filter', None)

        self.images = OrderedDict()

    @property
    def has_exposures(self):
        """ Bool indicating whether or not any exposures are left """
        return self.number_exposures > 0

    def estimate_duration(self, overhead=0 * u.s):
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
        duration = max([(self.primary_exptime + overhead) * self.primary_nexp,
                        (self.secondary_exptime + overhead) * self.secondary_nexp])
        self.logger.debug('Observation duration estimated as {}'.format(duration))
        return duration
