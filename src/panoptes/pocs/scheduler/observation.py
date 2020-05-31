import os
from astropy import units as u
from collections import OrderedDict

from panoptes.pocs.base import PanBase
from panoptes.pocs.scheduler.field import Field


class Observation(PanBase):

    @u.quantity_input(exptime=u.second)
    def __init__(self, field, exptime=120 * u.second, min_nexp=60,
                 exp_set_size=10, priority=100, filter_name=None, *args, **kwargs):
        """ An observation of a given `~pocs.scheduler.field.Field`.

        An observation consists of a minimum number of exposures (`min_nexp`) that
        must be taken at a set exposure time (`exptime`). These exposures come
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
            exptime {u.second} -- Exposure time for individual exposures
                (default: {120 * u.second})
            min_nexp {int} -- The minimum number of exposures to be taken for a
                given field (default: 60)
            exp_set_size {int} -- Number of exposures to take per set
                (default: {10})
            priority {int} -- Overall priority for field, with 1.0 being highest
                (default: {100})
            filter_name {str} -- Name of the filter to be used. If specified,
                will override the default filter name (default: {None}).

        """
        super().__init__(*args, **kwargs)

        assert isinstance(field, Field), self.logger.error("Must be a valid Field instance")

        assert exptime > 0.0, \
            self.logger.error(f"Exposure time (exptime={exptime}) must be greater than 0")

        assert min_nexp % exp_set_size == 0, \
            self.logger.error(
                f"Minimum number of exposures (min_nexp={min_nexp}) must be " +
                f"multiple of set size (exp_set_size={exp_set_size})")

        assert float(priority) > 0.0, self.logger.error(f"Priority must be 1.0 or larger, currently {priority}")

        self.field = field

        self.exptime = exptime
        self.min_nexp = min_nexp
        self.exp_set_size = exp_set_size
        self.exposure_list = OrderedDict()
        self.pointing_images = OrderedDict()

        self.priority = float(priority)

        self.filter_name = filter_name

        self._min_duration = self.exptime * self.min_nexp
        self._set_duration = self.exptime * self.exp_set_size

        self._image_dir = self.get_config('directories.images')
        self._directory = None
        self._seq_time = None

        self.merit = 0.0

        self.reset()

        self.logger.debug(f"Observation created: {self}")

    ##################################################################################################
    # Properties
    ##################################################################################################

    @property
    def status(self):
        """ Observation status

        Returns:
            dict: Dictionary containing current status of observation
        """

        equinox = 'J2000'
        try:
            equinox = self.field.coord.equinox.value
        except AttributeError:  # pragma: no cover
            equinox = self.field.coord.equinox

        status = {
            'current_exp': self.current_exp_num,
            'dec_mnt': self.field.coord.dec.value,
            'equinox': equinox,
            'exp_set_size': self.exp_set_size,
            'exptime': self.exptime.value,
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
        if self._directory is None:
            self.logger.warning(f'Setting observation directory to {self._image_dir}/{self.field.field_name}')
            self._directory = os.path.join(self._image_dir, self.field.field_name)

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

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def __str__(self):
        return "{}: {} exposures in blocks of {}, minimum {}, priority {:.0f}".format(
            self.field, self.exptime, self.exp_set_size, self.min_nexp, self.priority)
