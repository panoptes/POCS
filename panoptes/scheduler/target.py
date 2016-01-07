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

    def __init__(self, target_config):
        """Takes in a dictionary describing the target as read from the YAML
        file.  Populates the target properties from that dictionary.
        """
        self.config = load_config()
        self.logger = get_logger(self)

        assert 'name' in target_config, self.logger.warning("Problem with Target, trying adding a name")
        assert 'position' in target_config, self.logger.warning("Problem with Target, trying adding a position")
        assert isinstance(target_config['name'], str)

        name = target_config.get('name', None)
        sky_coord = None

        try:
            self.logger.debug("Loooking up coordinates for {}...".format(name))
            sky_coord = SkyCoord.from_name(name)
        except:
            self.logger.debug("Loooking up coordinates failed, using dict")
            sky_coord = SkyCoord(target_config['position'], frame=target_config.get('frame', 'icrs'))

        # try:
        super().__init__(name=name, coord=sky_coord)
        # except:
        #     raise PanError(msg="Can't load FixedTarget")

        self.coord.equinox = target_config.get('equinox', 'J2000')
        self.coord.obstime = target_config.get('epoch', 2000.)
        self.priority = target_config.get('priority', 1.0)

        # proper motion (is tuple of dRA/dt dDec/dt)
        proper_motion = target_config.get('proper_motion', '0.0 0.0').split()
        self.proper_motion = (proper_motion[0], proper_motion[1])

        # Add visits from config or a single default
        self.visits = []
        if 'visits' in target_config:
            obs_list = target_config['visits']
            for obs_dict in obs_list:
                self.visits.append(Observation(obs_dict))
        else:
            self.visits.append(Observation())

        self._current_visit = 0

##################################################################################################
# Properties
##################################################################################################

    @property
    def has_visits(self):
        """ Bool indicating whether or not any visits are left """
        num_visits = len(self.visits)
        _has_visits = (num_visits > 0) and (num_visits - 1 <= self._current_visit)
        self.logger.debug("has_visits: {}".format(_has_visits))

        return _has_visits

    @property
    def current_visit(self):
        """ Returns the current visit from the list """
        _current_visit = self.visits[self._current_visit]
        self.logger.debug("current_visit: {}".format(_current_visit))

        return _current_visit

##################################################################################################
# Methods
##################################################################################################

    def mark_visited(self):
        """ Mark the `current_visit` as complete and move to next """
        visit = self.current_visit

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
        for obs in self.visits:
            duration += obs.estimate_duration() + overhead
        self.logger.debug('Visit duration estimated as {}'.format(duration))
        return duration
