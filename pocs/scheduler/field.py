from astropy import units as u
from astropy.coordinates import SkyCoord

from astroplan import FixedTarget, ObservingBlock

from pocs import PanBase


class Field(ObservingBlock, PanBase):

    @u.quantity_input(exp_time=u.second)
    def __init__(self, name, position, exp_time=120 * u.second, min_num_exp=60, priority=100, **kwargs):
        """ An object representing an area to be observed

        A `Field` corresponds to an `~astroplan.ObservingBlock` and contains information
        about the center of the field (represented by an `astroplan.FixedTarget`), the priority,
        and the exposure time.

        Decorators:
            u.quantity_input

        Arguments:
            name {str} -- Name of the field, typically the name of object at center `position`
            position {str} -- Center of field, can be anything accepted by `~astropy.coordinates.SkyCoord`
            **kwargs {dict} -- Additional keywords to be passed to `astroplan.ObservingBlock`

        Keyword Arguments:
            exp_time {u.second} -- Exposure time for individual exposures (default: {120 * u.second})
            min_num_exp {int} -- The *minimum* number of exposures to be taken for given field (default: 60)
            priority {number} -- Overall priority for field, with 1.0 being highest (default: {100})
        """
        PanBase.__init__(self)

        priority = float(priority)
        assert priority > 1.0, self.logger.error("Priority must be 1.0 or larger")

        assert exp_time > 0.0, self.logger.error("Exposure time (exp_time) must be greater than 0")

        self.exp_time = exp_time
        self.min_num_exp = min_num_exp

        target = FixedTarget(SkyCoord(position), name=name, **kwargs)

        duration = self.exp_time * self.min_num_exp

        ObservingBlock.__init__(self, target, duration, priority)

        self._field_name = target.name.title().replace(' ', '').replace('-', '')

        self.logger.debug("Field created: {}".format(self.name))


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


##################################################################################################
# Methods
##################################################################################################


##################################################################################################
# Private Methods
##################################################################################################
