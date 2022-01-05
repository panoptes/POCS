import os
from abc import abstractmethod
from collections import OrderedDict
from contextlib import suppress

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import get_moon

from panoptes.utils import error
from panoptes.utils.library import load_module
from panoptes.utils.serializers import from_yaml
from panoptes.utils.time import current_time

from panoptes.pocs.base import PanBase
from panoptes.pocs.scheduler.observation.base import Observation


class BaseScheduler(PanBase):

    def __init__(self, observer, fields_list=None, fields_file=None, constraints=None, *args,
                 **kwargs):
        """Loads `~pocs.scheduler.field.Field`s from a field.

        Note:
            `~pocs.scheduler.field.Field` configurations passed via the `fields_list`
            will not be saved but will instead be turned into
            `~pocs.scheduler.observation.Observations`.

            Further `Observations` should be added directly via the `add_observation`
            method.

        Args:
            observer (`astroplan.Observer`): The physical location the scheduling
                will take place from.
            fields_list (list, optional): A list of valid target configurations.
            fields_file (str): YAML file containing field parameters.
            constraints (list, optional): List of `Constraints` to apply to each observation.
            *args: Arguments to be passed to `PanBase`
            **kwargs: Keyword args to be passed to `PanBase`
        """
        super().__init__(*args, **kwargs)

        assert isinstance(observer, Observer)

        self._observations = dict()
        self._current_observation = None
        self._fields_list = fields_list
        # Use the setter, which will force a file read.
        self.fields_file = fields_file

        self.observer = observer
        self.constraints = constraints or list()
        self.observed_list = OrderedDict()

        if self.get_config('scheduler.check_file', default=True):
            self.logger.debug("Reading fields list.")
            self.read_field_list()

        # Items common to each observation that shouldn't be computed each time.
        self.common_properties = None

    @property
    def status(self):
        return {
            'constraints': self.constraints,
            'current_observation': self.current_observation,
        }

    @property
    def observations(self):
        """Returns a dict of `~pocs.scheduler.observation.Observation` objects
        with `~pocs.scheduler.observation.Observation.field.field_name` as the key

        Note:
            `read_field_list` is called if list is None
        """
        if self.has_valid_observations is False:
            self.read_field_list()

        return self._observations

    @property
    def has_valid_observations(self):
        return len(self._observations.keys()) > 0

    @property
    def current_observation(self):
        """The observation that is currently selected by the scheduler

        Upon setting a new observation the `seq_time` is set to the current time
        and added to the `observed_list`. An old observation is reset (so that
        it can be used again - see `~pocs.scheduelr.observation.reset`). If the
        new observation is the same as the old observation, nothing is done. The
        new observation can also be set to `None` to specify there is no current
        observation.
        """
        return self._current_observation

    @current_observation.setter
    def current_observation(self, new_observation):

        if self.current_observation is None:
            # If we have no current observation but do have a new one, set seq_time
            # and add to the list
            if new_observation is not None:
                # Set the new seq_time for the observation
                new_observation.seq_time = current_time(flatten=True)

                # Add the new observation to the list
                self.observed_list[new_observation.seq_time] = new_observation
        else:
            # If no new observation, simply reset the current
            if new_observation is None:
                self.current_observation.reset()
            else:
                # If we have a new observation, check if same as old observation
                if self.current_observation.name != new_observation.name:
                    self.current_observation.reset()
                    new_observation.seq_time = current_time(flatten=True)

                    # Add the new observation to the list
                    self.observed_list[new_observation.seq_time] = new_observation

        self.logger.info("Setting new observation to {}".format(new_observation))
        self._current_observation = new_observation

    @property
    def fields_file(self):
        """Field configuration file

        A YAML list of config items, specifying a minimum of `name` and `position`
        for the `~pocs.scheduler.field.Field`. `Observation`s will be built from
        the list of fields.

        A file will be read by `~pocs.scheduler.priority.read_field_list` upon
        being set.

        Note:
            Setting a new `fields_file` will clear all existing fields

        """
        return self._fields_file

    @fields_file.setter
    def fields_file(self, new_file):
        self.clear_available_observations()

        self._fields_file = new_file
        self.read_field_list()

    @property
    def fields_list(self):
        """List of field configuration items

        A YAML list of config items, specifying a minimum of `name` and `position`
        for the `~pocs.scheduler.field.Field`. `Observation`s will be built from
        the list of fields.

        A file will be read by `~pocs.scheduler.priority.read_field_list` upon
        being set.

        Note:
            Setting a new `fields_list` will clear all existing fields

        """
        return self._fields_list

    @fields_list.setter
    def fields_list(self, new_list):
        self.clear_available_observations()

        self._fields_list = new_list
        self.read_field_list()

    @abstractmethod
    def get_observation(self, *args, **kwargs):
        """Get a valid observation."""
        raise NotImplementedError

    def clear_available_observations(self):
        """Reset the list of available observations"""
        # Clear out existing list and observations
        self.current_observation = None
        self._observations = dict()

    def reset_observed_list(self):
        """Reset the observed list """
        self.logger.debug('Resetting observed list')
        self.observed_list = OrderedDict()

    def observation_available(self, observation, time):
        """Check if observation is available at given time

        Args:
            observation (pocs.scheduler.observation): An Observation object
            time (astropy.time.Time): The time at which to check observation

        """
        return self.observer.target_is_up(time, observation.field, horizon=30 * u.degree)

    def add_observation(self, observation_config, **kwargs):
        """Adds an `Observation` to the scheduler.

        Args:
            observation_config (dict): Configuration dict for `Field` and `Observation`.
        """
        try:
            obs = Observation.from_dict(observation_config, **kwargs)
            self.logger.debug(f"Observation created: {obs!r}")

            # Add observation to scheduler.
            if obs.name in self._observations:
                self.logger.debug(f"Overriding existing entry for {obs.name=!r}")
            self._observations[obs.name] = obs
            self.logger.debug(f"{obs!r} added to {self}.")

        except Exception as e:
            raise error.InvalidObservation(f"Invalid field: {observation_config!r} {e!r}")

    def remove_observation(self, field_name):
        """Removes an `Observation` from the scheduler

        Args:
            field_name (str): Field name corresponding to entry key in `observations`

        """
        with suppress(Exception):
            obs = self._observations[field_name]
            del self._observations[field_name]
            self.logger.debug(f"Observation removed: {obs}")

    def read_field_list(self):
        """Reads the field file and creates valid `Observations`."""
        self.logger.debug(f'Reading fields from file: {self.fields_file}')
        if self._fields_file is not None:

            if not os.path.exists(self.fields_file):
                raise FileNotFoundError

            with open(self.fields_file, 'r') as f:
                self._fields_list = from_yaml(f.read())

        if self._fields_list is not None:
            for observation_config in self._fields_list:
                try:
                    self.add_observation(observation_config)
                except Exception as e:
                    self.logger.warning(f"Error adding observation: {e!r}")

    def set_common_properties(self, time):
        """Sets some properties common to all observations, such as end of night, moon, etc."""
        horizon_limit = self.get_config('location.observe_horizon', default=-18 * u.degree)
        self.common_properties = {
            'end_of_night': self.observer.tonight(time=time, horizon=horizon_limit)[-1],
            'moon': get_moon(time, self.observer.location),
            'observed_list': self.observed_list
        }
