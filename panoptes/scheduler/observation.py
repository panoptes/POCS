from astropy import units as u

from ..utils.logger import get_logger
from ..utils.config import load_config
from .exposure import Exposure


class Observation(object):

    def __init__(self, obs_config=dict(), cameras=None):
        """An object which describes a single observation.

        Each observation can have a number of different `Exposure`s based on the config settings.
        For each type of exposure ('primary' or 'secondary') there are `[type]_nexp` `Exposure`
            objects created. Each of these `Exposure`s has a list of cameras. (See `Exposure` for details)

        Example::

              - analyze: false
                primary_exptime: 300
                primary_filter: null
                primary_nexp: 3
                secondary_exptime: 300
                secondary_filter: null
                secondary_nexp: 3

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
                the YAML file, see Example.
            cameras(list[panoptes.camera]): A list of `panoptes.camera` objects to use for
                this observation.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        self.logger.debug("Camears for observation: {}".format(cameras))
        self.exposures = self._create_exposures(obs_config, cameras)
        self._current_exposure = 0
        self.exposures_iter = self.get_next_exposures()


##################################################################################################
# Properties
##################################################################################################

    @property
    def current_exposures(self):
        self.logger.debug("Getting current exposures")
        exps = []

        primary = self.exposures.get('primary', [])
        secondary = self.exposures.get('secondary', [])

        if len(primary) > self._current_exposure:
            e = primary[self._current_exposure]
            self.logger.debug("Exp: {}".format(e))
            exps.append(e)

        if len(secondary) > self._current_exposure:
            exps.append(secondary[self._current_exposure])

        self.logger.debug("Current exposures: {}".format(exps))
        return exps

    @property
    def has_exposures(self):
        """ Bool indicating whether or not any exposures are left """
        self.logger.debug("Checking if observation has exposures")

        has_exposures = self._current_exposure < self.num_exposures

        self.logger.debug("Observation has exposures: {}".format(has_exposures))

        return has_exposures

##################################################################################################
# Methods
##################################################################################################

    def get_next_exposures(self):
        """ Yields the next exposure """

        for exp_num in range(self.num_exposures):
            self._current_exposure = exp_num

            exposures = self.current_exposures
            self.logger.debug("Getting next exposures ({})".format(exposures))
            yield exposures

    def take_exposure(self):
        """ Take the next exposure """
        try:
            for exposures in self.exposures_iter:
                for num, exp in enumerate(exposures):
                    self.logger.debug("\t\t{} of {}".format(num + 1, len(self.exposures)))
                    exp.expose()
        except Exception as e:
            self.logger.warning("Can't take exposure from Observation: {}".format(e))

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

##################################################################################################
# Private Methods
##################################################################################################

    def _create_exposures(self, obs_config, cameras):
        self.logger.debug("Creating exposures")
        self.logger.debug("Available cameras: {}".format(cameras))
        self.logger.debug("Available cameras: {}".format([c.is_primary for c in cameras.values()]))

        primary_exptime = obs_config.get('primary_exptime', 10) * u.s
        primary_filter = obs_config.get('primary_filter', None)
        primary_nexp = obs_config.get('primary_nexp', 1)
        analyze = obs_config.get('primary_analyze', False)

        primary_exposures = [Exposure(
            exptime=primary_exptime,
            filter_type=primary_filter,
            analyze=analyze,
            cameras=[c for c in cameras.values() if c.is_primary],
        ) for n in range(primary_nexp)]
        self.logger.debug("Primary exposures: {}".format(primary_exposures))
        self.num_exposures = primary_nexp

        # secondary_exptime (assumes units of seconds, defaults to 120 seconds)
        secondary_exptime = obs_config.get('secondary_exptime', 120) * u.s
        secondary_nexp = obs_config.get('secondary_nexp', 0)
        secondary_filter = obs_config.get('secondary_filter', None)

        secondary_exposures = [Exposure(
            exptime=secondary_exptime,
            filter_type=secondary_filter,
            analyze=False,
            cameras=[c for c in cameras.values() if not c.is_primary],
        ) for n in range(secondary_nexp)]

        if secondary_nexp > primary_nexp:
            self.num_exposures = secondary_nexp

        self.logger.debug("Secondary exposures: {}".format(secondary_exposures))

        return {'primary': primary_exposures, 'secondary': secondary_exposures}
