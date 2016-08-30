from astropy import units as u

from .. import PanBase
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

        self.field = field

        self.exp_time = exp_time
        self.min_nexp = min_nexp
        self.exp_set_size = exp_set_size

        self.priority = float(priority)

        self._min_duration = self.exp_time * self.min_nexp
        self._set_duration = self.exp_time * self.exp_set_size

        self._seq_time = None

        self.current_exp = 0
        self.merit = 0.0

        self.metadata = dict()

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
        return {
            'current_exp': self.current_exp,
            'exp_set_size': self.exp_set_size,
            'exp_time': self.exp_time,
            'field_dec': self.field.coord.dec.value,
            'field_name': self.name,
            'field_ra': self.field.coord.ra.value,
            'merit': self.merit,
            'min_nexp': self.min_nexp,
            'minimum_duration': self.minimum_duration,
            'priority': self.priority,
            'seq_time': self.seq_time,
            'set_duration': self.set_duration,
        }

    def update_metadata(self, info):
        """ Update metadata info in the panpotes mongodb collection

        Add the `status` about the observation to the information from each camera
        and updates the `panoptes.observations` collection in mongo

        Args:
            info (dict): Info on the given exposure, with one dict per camera

        """
        for k, v in self.status().items():
            if isinstance(v, u.Quantity):
                v = v.value

            info[k] = v

        self.db.insert_current('observations', info)

##################################################################################################
# Private Methods
##################################################################################################

    def __str__(self):
        return "{}: {} exposures in blocks of {}, minimum {}, priority {:.0f}".format(
            self.field, self.exp_time, self.exp_set_size, self.min_nexp, self.priority)
