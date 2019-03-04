import os
import yaml

from collections import OrderedDict

from astroplan import Observer
from astropy import units as u

from pocs.base import PanBase
from pocs.utils import error
from pocs.utils import current_time
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation


class BaseScheduler(PanBase):

    def __init__(self, observer, fields_list=None, fields_file=None,
                 constraints=list(), *args, **kwargs):
        """Loads `~pocs.scheduler.field.Field`s from a field

        Note:
            `~pocs.scheduler.field.Field` configurations passed via the `fields_list`
            will not be saved but will instead be turned into
            `~pocs.scheduler.observation.Observations`.

            Further `Observations` should be added directly via the `add_observation`
            method.

        Args:
            observer (`astroplan.Observer`): The physical location the scheduling
                will take place from.
            fields_list (list, optional): A list of valid field configurations.
            fields_file (str): YAML file containing field parameters.
            constraints (list, optional): List of `Constraints` to apply to each
                observation.
            *args: Arguments to be passed to `PanBase`
            **kwargs: Keyword args to be passed to `PanBase`
        """
        PanBase.__init__(self, *args, **kwargs)

        assert isinstance(observer, Observer)

        self._fields_file = fields_file
        # Setting the fields_list directly will clobber anything
        # from the fields_file. It comes second so we can speicfically
        # clobber if passed.
        self._fields_list = fields_list
        self._observations = dict()

        self.observer = observer

        self.constraints = constraints

        self._current_observation = None
        self.observed_list = OrderedDict()

        if not self.config['scheduler'].get('check_file', False):
            self.logger.debug("Reading initial set of fields")
            self.read_field_list()


##########################################################################
# Properties
##########################################################################

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
        if new_file is not None:
            assert os.path.exists(new_file), \
                self.logger.error("Cannot load field list: {}".format(new_file))
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

##########################################################################
# Methods
##########################################################################

    def clear_available_observations(self):
        """Reset the list of available observations"""
        # Clear out existing list and observations
        self.current_observation = None
        self._observations = dict()

    def get_observation(self, time=None, show_all=False):
        """Get a valid observation

        Args:
            time (astropy.time.Time, optional): Time at which scheduler applies,
                defaults to time called
            show_all (bool, optional): Return all valid observations along with
                merit value, defaults to False to only get top value

        Returns:
            tuple or list: A tuple (or list of tuples) with name and score of ranked observations
        """
        raise NotImplementedError

    def status(self):
        return {
            'constraints': self.constraints,
            'current_observation': self.current_observation,
        }

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

    def add_observation(self, field_config):
        """Adds an `Observation` to the scheduler

        Args:
            field_config (dict): Configuration items for `Observation`
        """
        if 'exposure' in field_config:
            field_config['exposure'] = float(field_config['exposure']) * u.second

        self.logger.debug("Adding {} to scheduler", field_config['name'])
        field = Field(field_config['name'], field_config['position'])

        try:
            obs = Observation(field, **field_config)
        except Exception:
            raise error.InvalidObservation(
                "Skipping invalid field config: {}".format(field_config))
        else:
            if field.name in self._observations:
                self.logger.debug("Overriding existing entry for {}".format(field.name))
            self._observations[field.name] = obs

    def remove_observation(self, field_name):
        """Removes an `Observation` from the scheduler

        Args:
            field_name (str): Field name corresponding to entry key in `observations`

        """
        try:
            obs = self._observations[field_name]
            del self._observations[field_name]
            self.logger.debug("Observation removed: {}".format(obs))
        except Exception:
            pass

    def read_field_list(self):
        """Reads the field file and creates valid `Observations` """
        if self._fields_file is not None:
            self.logger.debug('Reading fields from file: {}'.format(self.fields_file))

            if not os.path.exists(self.fields_file):
                raise FileNotFoundError

            with open(self.fields_file, 'r') as f:
                self._fields_list = yaml.load(f.read())

        if self._fields_list is not None:
            for field_config in self._fields_list:
                try:
                    self.add_observation(field_config)
                except AssertionError:
                    self.logger.debug("Skipping duplicate field.")
                except Exception as e:
                    self.logger.warning("Error adding field: {}", e)

##########################################################################
# Utility Methods
##########################################################################

##########################################################################
# Private Methods
##########################################################################
