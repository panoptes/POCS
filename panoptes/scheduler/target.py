import astropy.units as u
from astropy.coordinates import SkyCoord

from astroplan import FixedTarget

from ..utils.error import *
from ..utils.logger import get_logger
from ..utils.config import load_config

from .observation import Observation

# ----------------------------------------------------------------------------
# Target Class
# ----------------------------------------------------------------------------


class Target(FixedTarget):

    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """

    def __init__(self, target_config, cameras=None, **kwargs):
        """  A FixedTarget object that we want to gather data about.

        A `Target` represents not only the actual object in the night sky
        (via the `self.coord` astropy.SkyCoord attribute) but also the concept
        of a `visit`, which is a list of `Observation`s.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        assert 'name' in target_config, self.logger.warning("Problem with Target, trying adding a name")
        assert 'position' in target_config, self.logger.warning("Problem with Target, trying adding a position")
        assert isinstance(target_config['name'], str)

        name = target_config.get('name', None)
        sky_coord = None

        try:
            self.logger.debug("Looking up coordinates for {}...".format(name))
            sky_coord = SkyCoord.from_name(name)
        except:
            self.logger.debug("Looking up coordinates failed, using dict")
            sky_coord = SkyCoord(target_config['position'], frame=target_config.get('frame', 'icrs'))

        super().__init__(name=name, coord=sky_coord, **kwargs)

        self.coord.equinox = target_config.get('equinox', 'J2000')
        self.coord.obstime = target_config.get('epoch', 2000.)
        self.priority = target_config.get('priority', 1.0)

        # proper motion (is tuple of dRA/dt dDec/dt)
        proper_motion = target_config.get('proper_motion', '0.0 0.0').split()
        self.proper_motion = (proper_motion[0], proper_motion[1])

        # Each target as a `visit` that is a list of Observations
        self.logger.debug("Target cameras: {}".format(cameras))
        self.visit = [Observation(od, cameras=cameras) for od in target_config.get('visit', [{}])]

        self._current_observation = 0

##################################################################################################
# Properties
##################################################################################################

    @property
    def done_visiting(self):
        """ Bool indicating whether or not any observations are left """
        self.logger.debug("Checking if done with all visits")
        done_visiting = all([not o.has_exposures for o in self.visit])
        self.logger.debug("done_visiting: {}".format(done_visiting))

        return done_visiting

    @property
    def current_observation(self):
        """ Returns the current observation from the list """
        current_obs = self.visit[self._current_observation]
        self.logger.debug("Current Observation: {}".format(current_obs))

        return current_obs

    @property
    def reference_exposure(self):
        ref_exp = None

        try:
            first_visit = self.visit[0]
            first_exposure = first_visit.exposures.get('primary', [])[0]

            if first_exposure.images_exist:
                ref_exp = first_exposure.images[0]
        except Exception as e:
            self.logger.debug("Can't get reference exposure: {}".format(e))

        return ref_exp

##################################################################################################
# Methods
##################################################################################################

    def mark_observation_complete(self):
        """ Mark the `current_visit` as complete and move to next """
        self._current_observation = self._current_observation + 1

    def estimate_visit_duration(self, overhead=0 * u.s):
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
        duration = 0 * u.s
        for obs in self.visit:
            duration += obs.estimate_duration() + overhead
        self.logger.debug('Visit duration estimated as {}'.format(duration))
        return duration
