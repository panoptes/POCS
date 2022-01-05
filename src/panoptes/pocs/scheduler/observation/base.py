import os
from collections import OrderedDict, defaultdict
from contextlib import suppress
from pathlib import Path
from typing import Dict, List, Optional

from astropy import units as u
from panoptes.utils.library import load_module
from pydantic.dataclasses import dataclass

from panoptes.utils.utils import get_quantity_value, listify
from panoptes.utils import error
from panoptes.pocs.base import PanBase
from panoptes.pocs.scheduler.field import Field


@dataclass
class Exposure:
    image_id: str
    path: Path
    metadata: dict
    is_primary: bool = False


class Observation(PanBase):

    def __init__(self, field, exptime=120 * u.second, min_nexp=60, exp_set_size=10, priority=100,
                 filter_name=None, dark=False, *args, **kwargs):
        """ An observation of a given `panoptes.pocs.scheduler.field.Field`.

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
            dark (bool, optional): If True, exposures should be taken with the shutter closed.
                Default: False.
        """
        super().__init__(*args, **kwargs)

        exptime = get_quantity_value(exptime, u.second) * u.second

        if not isinstance(field, Field):
            raise TypeError(f"field must be a valid Field instance, got {type(field)}.")

        if exptime < 0 * u.second:  # 0 second exposures correspond to bias frames
            raise ValueError(f"Exposure time must be greater than or equal to 0, got {exptime}.")

        if not min_nexp % exp_set_size == 0:
            raise ValueError(f"Minimum number of exposures (min_nexp={min_nexp}) must be "
                             f"a multiple of set size (exp_set_size={exp_set_size}).")

        if not float(priority) > 0.0:
            raise ValueError("Priority must be larger than 0.")

        self.field = field
        self.dark = dark

        self._exptime = exptime
        self.min_nexp = min_nexp
        self.exp_set_size = exp_set_size

        self.exposure_list: Dict[str, List[Exposure]] = defaultdict(list)
        self.pointing_images: Dict[str, Path] = OrderedDict()

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

    ################################################################################################
    # Properties
    ################################################################################################

    @property
    def status(self) -> Dict:
        """ Observation status.

        Returns:
            dict: Dictionary containing current status of observation.
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
            'dark': self.dark
        }

        return status

    @property
    def exptime(self):
        return self._exptime

    @exptime.setter
    def exptime(self, value):
        self._exptime = get_quantity_value(value, u.second) * u.second

    @property
    def exptimes(self):
        """Exposure time as a list."""
        return listify(self.exptime)

    @property
    def minimum_duration(self):
        """ Minimum amount of time to complete the observation """
        return self._min_duration

    @property
    def set_duration(self):
        """ Amount of time per set of exposures."""
        return self._set_duration

    @property
    def name(self):
        """ Name of the `~pocs.scheduler.field.Field` associated with the observation."""
        return self.field.name

    @property
    def seq_time(self):
        """ The time at which the observation was selected by the scheduler.

        This is used for path name construction.
        """
        return self._seq_time

    @seq_time.setter
    def seq_time(self, time):
        self._seq_time = time

    @property
    def directory(self) -> Path:
        """Return the directory for this Observation.

        This return the base directory for the Observation. This does *not* include
        the subfolders for each of the cameras.

        Returns:
            str: Full path to base directory.
        """
        if self._directory is None:
            self._directory = os.path.join(self._image_dir, self.field.field_name)
            self.logger.warning(f'Observation directory set to {self._directory}')

        return self._directory

    @property
    def current_exp_num(self) -> int:
        """ Return the current number of exposures.

        Returns the maximum size of the exposure list from each camera.

        Returns:
            int: The size of `self.exposure_list`.
        """
        try:
            return max([len(exposures) for exposures in self.exposure_list.values()])
        except ValueError:
            return 0

    @property
    def first_exposure(self) -> Optional[List[Dict[str, Exposure]]]:
        """ Return the first exposure information.

        Returns:
            tuple: `image_id` and full path of the first exposure from the primary camera.
        """
        return self.get_exposure(0)

    @property
    def last_exposure(self) -> Optional[List[Dict[str, Exposure]]]:
        """ Return the latest exposure information.

        Returns:
            tuple: `image_id` and full path of most recent exposure from the primary camera
        """
        return self.get_exposure(number=-1)

    def get_exposure(self, number: int = 0) -> Optional[List[Dict[str, Exposure]]]:
        """Returns the given exposure number."""
        exposure = list()
        try:
            if len(self.exposure_list) > 0:
                for cam_name, exposure_list in self.exposure_list.items():
                    with suppress(IndexError):
                        exposure.append({cam_name: exposure_list[number]})
        except Exception:
            self.logger.debug(f'No exposures available.')
        finally:
            return exposure

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

    @property
    def set_is_finished(self):
        """ Check if the current observing block has finished, which is True when the minimum
        number of exposures have been obtained and and integer number of sets have been completed.
        Returns:
            bool: True if finished, False if not.
        """
        # Check the min required number of exposures have been obtained
        has_min_exposures = self.current_exp_num >= self.min_nexp

        # Check if the current set is finished
        this_set_finished = self.current_exp_num % self.exp_set_size == 0

        return has_min_exposures and this_set_finished

    ################################################################################################
    # Methods
    ################################################################################################

    def add_to_exposure_list(self, cam_name: str, exposure: Exposure):
        """Add the exposure to the list and mark as most recent"""
        self.exposure_list[cam_name].append(exposure)

    def reset(self):
        """Resets the exposure information for the observation """
        self.logger.debug(f"Resetting observation {self}")

        self.exposure_list.clear()
        self.merit = 0.0
        self.seq_time = None

    ################################################################################################
    # Private Methods
    ################################################################################################

    def __str__(self):
        return f"{self.field}: {self.exptime} exposures " \
               f"in blocks of {self.exp_set_size}, " \
               f"minimum {self.min_nexp}, " \
               f"priority {self.priority:.0f}"

    ################################################################################################
    # Class Methods
    ################################################################################################

    @classmethod
    def from_dict(cls,
                  observation_config: Dict,
                  field_class='panoptes.pocs.scheduler.field.Field',
                  observation_class='panoptes.pocs.scheduler.observation.base.Observation'):
        """Creates an `Observation` object from config dict.

        Args:
            observation_config (dict): Configuration for `Field` and `Observation`.
            field_class (str, optional): The full name of the python class to be used as
                default for the observation's Field. This can be overridden by specifying the "type"
                item under the observation_config's "field" key.
                Default: `panoptes.pocs.scheduler.field.Field`.
            observation_class (str, optional): The full name of the python class to be used
                as default for the observation object. This can be overridden by specifying the
                "type" item under the observation_config's "observation" key.
                Default: `panoptes.pocs.scheduler.observation.base.Observation`.
        """
        observation_config = observation_config.copy()

        field_config = observation_config.get("field", {})
        field_type_name = field_config.pop("type", field_class)

        obs_config = observation_config.get("observation", {})
        obs_type_name = obs_config.pop("type", observation_class)

        try:
            # Make the field
            field = load_module(field_type_name)(**field_config)

            # Make the observation
            obs = load_module(obs_type_name)(field=field, **obs_config)
        except Exception as e:
            raise error.InvalidObservation(f"Invalid field: {observation_config!r} {e!r}")
        else:
            return obs
