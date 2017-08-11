from astropy import units as u
from collections import OrderedDict

from .. import PanBase
from ..utils import listify
from .field import Field


class Observation(PanBase):

    @u.quantity_input(exp_time=u.second)
    def __init__(self, field, exp_time=120 * u.second, min_nexp=60,
                 exp_set_size=10, priority=100, **kwargs):
        """ An observation of a given `~pocs.scheduler.field.Field`.

        An observation consists of a minimum number of exposures (`min_nexp`) that
        must be taken at a set exposure time (`exp_time`). These exposures come
        in sets of a certain size (`exp_set_size`) where the minimum number of
        exposures  must be an integer multiple of the set size.

        Note:
            An observation may consist of more exposures than `min_nexp` but
            exposures will always come in groups of `exp_set_size`.

        Decorators:
            u.quantity_input

        Arguments:
            field {`pocs.scheduler.field.Field`} -- An object representing the
            field to be captured

        Keyword Arguments:
            exp_time {u.second} -- Exposure time for individual exposures
                (default: {120 * u.second})
            min_nexp {int} -- The minimum number of exposures to be taken for a
                given field (default: 60)
            exp_set_size {int} -- Number of exposures to take per set
                (default: {10})
            priority {int} -- Overall priority for field, with 1.0 being highest
                (default: {100})

        """
        PanBase.__init__(self)

        assert isinstance(field, Field), self.logger.error("Must be a valid Field instance")

        assert exp_time > 0.0, \
            self.logger.error("Exposure time (exp_time) must be greater than 0")

        assert min_nexp % exp_set_size == 0, \
            self.logger.error("Minimum number of exposures (min_nexp) must be multiple of set size (exp_set_size)")

        assert float(priority) > 0.0, self.logger.error("Priority must be 1.0 or larger")

        self.current_exp = 0

        self.field = field

        self.exp_time = exp_time
        self.min_nexp = min_nexp
        self.exp_set_size = exp_set_size
        self.exposure_list = OrderedDict()

        self.priority = float(priority)

        self._min_duration = self.exp_time * self.min_nexp
        self._set_duration = self.exp_time * self.exp_set_size

        self.pointing_image = None

        self._seq_time = None

        self.merit = 0.0

        self.logger.debug("Observation created: {}".format(self))


##################################################################################################
# Properties
##################################################################################################

    @property
    def minimum_duration(self):
        """ Minimum amount of time to complete the observation """
        return self._min_duration

    @property
    def set_duration(self):
        """ Amount of time per set of exposures """
        return self._set_duration

    @property
    def name(self):
        """ Name of the `~pocs.scheduler.field.Field` associated with the observation """
        return self.field.name

    @property
    def seq_time(self):
        """ The time at which the observation was selected by the scheduler

        This is used for path name construction
        """
        return self._seq_time

    @seq_time.setter
    def seq_time(self, time):
        self._seq_time = time

    @property
    def first_exposure(self):
        """ Return the latest exposure information

        Returns:
            tuple: `image_id` and full path of most recent exposure from the primary camera
        """
        try:
            return list(self.exposure_list.items())[0]
        except IndexError:
            self.logger.warning("No exposure available")

    @property
    def last_exposure(self):
        """ Return the latest exposure information

        Returns:
            tuple: `image_id` and full path of most recent exposure from the primary camera
        """
        try:
            return list(self.exposure_list.items())[-1]
        except IndexError:
            self.logger.warning("No exposure available")


##################################################################################################
# Methods
##################################################################################################

    def reset(self):
        """Resets the exposure values for the observation """
        self.logger.debug("Resetting observation {}".format(self))

        self.current_exp = 0
        self.merit = 0.0
        self.seq_time = None

    def status(self):
        """ Observation status

        Returns:
            dict: Dictonary containing current status of observation
        """
        status = {
            'current_exp': self.current_exp,
            'dec_mnt': self.field.coord.dec.value,
            'equinox': self.field.coord.equinox,
            'exp_set_size': self.exp_set_size,
            'exp_time': self.exp_time.value,
            'field_dec': self.field.coord.dec.value,
            'field_name': self.name,
            'field_ra': self.field.coord.ra.value,
            'merit': self.merit,
            'min_nexp': self.min_nexp,
            'minimum_duration': self.minimum_duration.value,
            'priority': self.priority,
            'ra_mnt': self.field.coord.ra.value,
            'seq_time': self.seq_time,
            'set_duration': self.set_duration.value,
        }

        return status


##################################################################################################
# Private Methods
##################################################################################################

    def __str__(self):
        return "{}: {} exposures in blocks of {}, minimum {}, priority {:.0f}".format(
            self.field, self.exp_time, self.exp_set_size, self.min_nexp, self.priority)


class DitheredObservation(Observation):

    """ Observation that dithers to different points

    Dithered observations will consist of both multiple exposure time as well as multiple
    `Field` locations, which are used as a simple dithering mechanism

    Note:
        For now the new observation must be created like a normal `Observation`,
        with one `exp_time` and one `field`. Then use direct property assignment
        for the list of `exp_time` and `field`. New `field`/`exp_time` combos can
        more conveniently be set with `add_field`
    """

    def __init__(self, *args, **kwargs):
        super(DitheredObservation, self).__init__(min_nexp=1, exp_set_size=1, *args, **kwargs)

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
        return self.current_exp % len(self._exp_time)

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
