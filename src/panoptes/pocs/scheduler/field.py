"""Field utilities used by the scheduler.

Defines the Field class, a thin wrapper around astroplan.FixedTarget with
additional conveniences for naming and construction from AltAz coordinates.
"""
from astroplan import FixedTarget
from astropy.coordinates import SkyCoord
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec

from panoptes.pocs.base import PanBase


class Field(FixedTarget, PanBase):
    """Represents the center of an observing field (target) for scheduling."""
    def __init__(self, name, position, equinox="J2000", *args, **kwargs):
        """An object representing an area to be observed

        A `Field` corresponds to an `~astroplan.ObservingBlock` and contains information
        about the center of the field (represented by an `astroplan.FixedTarget`).

        Arguments:
            name {str} -- Name of the field, typically the name of object at
                center `position`.
            position {str} -- Center of field, can be anything accepted by
                `~astropy.coordinates.SkyCoord`.
            **kwargs {dict} -- Additional keywords to be passed to
                `astroplan.ObservingBlock`.

        """
        PanBase.__init__(self, *args, **kwargs)

        # Force an equinox if they pass None (legacy).
        equinox = equinox or "J2000"

        # Convert name to string to handle numeric names from YAML
        name = str(name)

        super().__init__(SkyCoord(position, equinox=equinox, frame="icrs"), name=name, **kwargs)

        self._field_name = self.name.title().replace(" ", "").replace("-", "")
        if not self._field_name:
            raise ValueError("Name is empty")

    @property
    def field_name(self):
        """Flattened field name appropriate for paths"""
        return self._field_name

    def __str__(self):
        return self.name

    @classmethod
    def from_altaz(cls, name, alt, az, location, time=None, *args, **kwargs):
        """Create a Field form AltAz coords, a location, and optional time."""
        time = time or current_time()
        # Construct RA/Dec coords from the Alt Az.
        flat_coords = altaz_to_radec(alt=alt, az=az, location=location, obstime=time)

        return cls(name, flat_coords)
