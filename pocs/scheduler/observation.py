import os
from astropy import units as u
from collections import OrderedDict

from pocs.base import PanBase
from pocs.scheduler.field import Field


class Observation(PanBase):

    @u.quantity_input(exp_time=u.second)
    def __init__(self, field, exp_time=120 * u.second, min_nexp=60, max_nexp=None,
                 exp_set_size=10, priority=100, **kwargs):
        """An observation of a given `~pocs.scheduler.field.Field`.

        An observation consists of a minimum number of exposures (`min_nexp`) that
        must be taken at a set exposure time (`exp_time`). These exposures come
        in sets of a certain size (`exp_set_size`) where the minimum number of
        exposures  must be an integer multiple of the set size.

        Note:
            Both the `min_nexp` and the `max_nexp` must be multiples of the
            `exp_set_size`. If `max_nexp` is less than `min_nexp` then `max_nexp`
            will take priority.

        Decorators:
            u.quantity_input

        Arguments:
            field (`~pocs.scheduler.field.Field`): An object representing the
                field to be captured.
            exp_time (`astropy.unit.Quantity`, optional): The exposure time in
                seconds, default 120.
            min_nexp (int, optional): The minimum number of exposures to take, default 60.
            max_nexp (int, optional): The maxiumum number of exposures to take,
                default `None`, which will dwell on the field as long as possible.
                See also the note in the docstring.
            exp_set_size (int, optional): Number of exposures taken per set, default 10.
            priority (int, optional): The priority of the target, default 100.
            **kwargs: Description
        """
        PanBase.__init__(self)

        assert isinstance(field, Field), self.logger.error("Must be a valid Field instance")

        assert exp_time > 0.0, \
            self.logger.error("Exposure time (exp_time) must be greater than 0")

        assert min_nexp % exp_set_size == 0, \
            self.logger.error('min_nexp exposures must occur in blocks of exp_set_size')

        if max_nexp:
            assert max_nexp % exp_set_size == 0, \
                self.logger.error('max_nexp exposures must occur in blocks of exp_set_size')

        # Make sure max_nexp is larger than min_nexp if given.
        if max_nexp and max_nexp < min_nexp:
            self.logger.debug(f'Max number of exposures less than minimum, changing minimum.')
            min_nexp = max_nexp

        assert float(priority) > 0.0, self.logger.error("Priority must be 1.0 or larger")

        self.field = field

        self.exp_time = exp_time
        self.min_nexp = min_nexp
        self.max_nexp = max_nexp
        self.exp_set_size = exp_set_size
        self.exposure_list = OrderedDict()
        self.pointing_images = OrderedDict()

        self.priority = float(priority)

        self._min_duration = self.exp_time * self.min_nexp
        self._set_duration = self.exp_time * self.exp_set_size

        self._image_dir = self.config['directories']['images']
        self._seq_time = None

        self.merit = 0.0

        self.reset()

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
    def directory(self):
        """Return the directory for this Observation.

        This return the base directory for the Observation. This does *not* include
        the subfolders for each of the cameras.

        Returns:
            str: Full path to base directory.
        """
        try:
            return self._directory
        except AttributeError:
            self._directory = os.path.join(self._image_dir,
                                           'fields',
                                           self.field.field_name)
            return self._directory

    @property
    def current_exp_num(self):
        """ Return the current number of exposures.

        Returns:
            int: The size of `self.exposure_list`.
        """
        return len(self.exposure_list)

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

    @property
    def pointing_image(self):
        """Return the last pointing image.

        Returns:
            tuple: `image_id` and full path of most recent pointing image from
                the primary camera.
        """
        try:
            return list(self.pointing_images.items())[-1]
        except IndexError:
            self.logger.warning("No pointing image available")


##################################################################################################
# Methods
##################################################################################################

    def reset(self):
        """Resets the exposure information for the observation """
        self.logger.debug("Resetting observation {}".format(self))

        self.exposure_list = OrderedDict()
        self.merit = 0.0
        self.seq_time = None

    def status(self):
        """ Observation status

        Returns:
            dict: Dictonary containing current status of observation
        """

        try:
            equinox = self.field.coord.equinox.value
        except AttributeError:
            equinox = self.field.coord.equinox
        except Exception:
            equinox = 'J2000'

        status = {
            'current_exp': self.current_exp_num,
            'dec_mnt': self.field.coord.dec.value,
            'equinox': equinox,
            'exp_set_size': self.exp_set_size,
            'exp_time': self.exp_time.value,
            'field_dec': self.field.coord.dec.value,
            'field_name': self.name,
            'field_ra': self.field.coord.ra.value,
            'merit': self.merit,
            'min_nexp': self.min_nexp,
            'max_nexp': self.max_nexp,
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
        str_repr = "{}: {} exposures in blocks of {}, min/max {}/{}, priority {:.0f}".format(
            self.field.name,
            self.exp_time,
            self.exp_set_size,
            self.min_nexp,
            self.max_nexp,
            self.priority
        )

        return str_repr
