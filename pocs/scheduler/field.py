from astropy.coordinates import SkyCoord
from astroplan import FixedTarget

from pocs import PanBase


class Field(FixedTarget, PanBase):

    def __init__(self, name, position, **kwargs):
        """ An object representing an area to be observed

        A `Field` corresponds to an `~astroplan.ObservingBlock` and contains information
        about the center of the field (represented by an `astroplan.FixedTarget`).

        Arguments:
            name {str} -- Name of the field, typically the name of object at center `position`
            position {str} -- Center of field, can be anything accepted by `~astropy.coordinates.SkyCoord`
            **kwargs {dict} -- Additional keywords to be passed to `astroplan.ObservingBlock`

        """
        PanBase.__init__(self)

        super().__init__(SkyCoord(position), name=name, **kwargs)

        self._field_name = self.name.title().replace(' ', '').replace('-', '')


##################################################################################################
# Properties
##################################################################################################

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

    def __str__(self):
        return self.name
