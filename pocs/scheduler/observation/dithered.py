from astropy import units as u

from contextlib import suppress
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation

from pocs.utils import listify


class DitheredObservation(Observation):

    """ Observation that dithers to different points.

    Dithered observations will consist of both multiple exposure time as well as multiple
    `Field` locations, which are used as a simple dithering mechanism.

    Note:
        For now the new observation must be created like a normal `Observation`,
        with one `exp_time` and one `field`. Then use direct property assignment
        for the list of `exp_time` and `field`. New `field`/`exp_time` combos can
        more conveniently be set with `add_field`
    """

    def __init__(self, *args, **kwargs):
        super(DitheredObservation, self).__init__(*args, **kwargs)

        # Set initial list to original values
        self._exp_time = listify(self.exp_time)
        self._field = listify(self.field)

        self.extra_config = kwargs

    @property
    def exp_time(self):
        exp_time = self._exp_time[self.exposure_index]

        if not isinstance(exp_time, u.Quantity):
            exp_time *= u.second

        return exp_time

    @exp_time.setter
    def exp_time(self, values):
        assert all(t > 0.0 for t in listify(values)), \
            self.logger.error("Exposure times (exp_time) must be greater than 0")

        self._exp_time = listify(values)

    @property
    def field(self):
        return self._field[self.exposure_index]

    @field.setter
    def field(self, values):
        assert all(isinstance(f, Field) for f in listify(values)), \
            self.logger.error("All fields must be a valid Field instance")

        self._field = listify(values)

    @property
    def exposure_index(self):
        _exp_index = 0
        with suppress(AttributeError):
            _exp_index = self.current_exp_num % len(self._exp_time)

        return _exp_index

    def add_field(self, new_field, new_exp_time):
        """ Add a new field to observe along with exposure time

        Args:
            new_field (pocs.scheduler.field.Field): A `Field` object
            new_exp_time (float): Number of seconds to expose

        """
        self.logger.debug("Adding new field {} {}".format(new_field, new_exp_time))
        self._field.append(new_field)
        self._exp_time.append(new_exp_time)

    def __str__(self):
        return "DitheredObservation: {}: {}".format(self._field, self._exp_time)
