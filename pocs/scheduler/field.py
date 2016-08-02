from astropy import units as u
from astropy.coordinates import SkyCoord

from astroplan import FixedTarget, ObservingBlock

from pocs import PanBase


class Field(ObservingBlock, PanBase):

    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """

    @u.quantity_input(exp_time=u.second)
    def __init__(self, name, position, exp_time=120 * u.second, priority=100, **kwargs):
        """  An object representing an area to be observed

        A `Field` corresponds to an `~astroplan.ObservingBlock` and contains information
        about the center of the field (represented by an `astroplan.FixedTarget`), the priority,
        and the exposure time.

        """
        PanBase.__init__(self)

        priority = float(priority)
        assert priority > 1.0, self.logger.error("Priority must be 1.0 or larger")

        assert exp_time > 0.0, self.logger.error("Exposure time (exp_time) must be greater than 0")

        target = FixedTarget(SkyCoord(position), name=name, **kwargs)

        ObservingBlock.__init__(self, target, exp_time, priority)

        self._field_name = target.name.title().replace(' ', '').replace('-', '')

        self.logger.debug("Target created: {}".format(self.name))


##################################################################################################
# Properties
##################################################################################################

    @property
    def name(self):
        """ Field Name """
        return self.target.name

    @property
    def field_name(self):
        """ Flattened field name appropriate for paths """
        return self._field_name

    @property
    def exp_time(self):
        """ Same as `duration` """
        return self.duration


##################################################################################################
# Methods
##################################################################################################


##################################################################################################
# Private Methods
##################################################################################################
