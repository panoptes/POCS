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
        # name
        self.config = load_config()

        self.logger = get_logger(self)

        assert 'name' in target_config, self.logger.warning("Problem with Target, trying adding a name")
        assert 'position' in target_config, self.logger.warning("Problem with Target, trying adding a position")
        assert isinstance(target_config['name'], str)

        # try:
        super().__init__(
            name=target_config.get('name', None),
            coord=SkyCoord(target_config['position'], frame=target_config.get('frame', 'icrs'))
        )
        # except:
        #     raise PanError(msg="Can't load FixedTarget")

        self.coord.equinox = target_config.get('equinox', 'J2000')
        self.coord.obstime = target_config.get('epoch', 2000.)
        self.priority = target_config.get('priority', 1.0)

        # proper motion (is tuple of dRA/dt dDec/dt)
        proper_motion = target_config.get('proper_motion', '0.0 0.0').split()
        self.proper_motion = (proper_motion[0], proper_motion[1])

        # visit
        self.visit = []
        if 'visit' in target_config:
            obs_list = target_config['visit']
            for obs_dict in obs_list:
                self.visit.append(Observation(obs_dict))

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
