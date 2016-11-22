import os
import yaml

from astroplan import Observer
from astropy import units as u

from astropy.coordinates import get_moon

from .. import PanBase
from ..utils import current_time
from ..utils import listify

from .field import Field
from .observation import Observation


class Scheduler(PanBase):

    def __init__(self, observer, fields_list=None, fields_file=None, constraints=list(), *args, **kwargs):
        """Loads `~pocs.scheduler.field.Field`s from a field

        Note:
            `~pocs.scheduler.field.Field` configurations passed via the `fields_list`
            will not be saved but will instead be turned into `~pocs.scheduler.observation.Observations`.
            Further `Observations` should be added directly via the `add_observation`
            method.

        Args:
            observer (`astroplan.Observer`): The physical location the scheduling will take place from
            fields_list (list, optional): A list of valid field configurations
            fields_file (str): YAML file containing field parameters
            constraints (list, optional): List of `Constraints` to apply to each
                observation
            *args: Arguments to be passed to `PanBase`
            **kwargs: Keyword args to be passed to `PanBase`
        """
        PanBase.__init__(self, *args, **kwargs)

        assert isinstance(observer, Observer)

        self._fields_file = fields_file
        self._fields_list = fields_list
        self._observations = dict()

        self.observer = observer

        self.constraints = constraints

        self._current_observation = None

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
        if len(self._observations.keys()) == 0:
            self.read_field_list()

        return self._observations

    @property
    def current_observation(self):
        """ The observation that is currently selected by the scheduler """
        return self._current_observation

    @current_observation.setter
    def current_observation(self, new_observation):
        # First reset the existing if different

        # This is ugly
        if self.current_observation is not None:
            if new_observation is not None:
                if self.current_observation.name != new_observation.name:
                    self.current_observation.reset()
                    new_observation.seq_time = current_time(flatten=True)
            else:
                self.current_observation.reset()
        else:
            if new_observation is not None:
                # Set the new seq_time for the observation
                new_observation.seq_time = current_time(flatten=True)

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
        # Clear out existing list and observations
        self._fields_list = None
        self._observations = dict()

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
        # Clear out existing list and observations
        self._fields_file = None
        self._observations = dict()

        self._fields_list = new_list
        self.read_field_list()


##########################################################################
# Methods
##########################################################################

    def status(self):
        return {
            'constraints': self.constraints,
            'current_observation': self.current_observation,
        }

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
        if time is None:
            time = current_time()

        valid_obs = {obs: 1.0 for obs in self.observations}
        best_obs = []

        common_properties = {
            'end_of_night': self.observer.tonight(time=time, horizon=-18 * u.degree)[-1],
            'moon': get_moon(time, self.observer.location)
        }

        for constraint in listify(self.constraints):
            self.logger.debug("Checking Constraint: {}".format(constraint))
            for obs_name, observation in self.observations.items():
                if obs_name in valid_obs:
                    self.logger.debug("\tObservation: {}".format(obs_name))

                    veto, score = constraint.get_score(
                        time, self.observer, observation, **common_properties)

                    self.logger.debug("\t\tScore: {}\tVeto: {}".format(score, veto))

                    if veto:
                        self.logger.debug("\t\t{} vetoed by {}".format(obs_name, constraint))
                        del valid_obs[obs_name]
                        continue

                    valid_obs[obs_name] += score

        for obs_name, score in valid_obs.items():
            valid_obs[obs_name] += self.observations[obs_name].priority

        if len(valid_obs) > 0:
            # Sort the list by highest score (reverse puts in correct order)
            best_obs = sorted(valid_obs.items(), key=lambda x: x[1])[::-1]

            top_obs = best_obs[0]

            # Check new best against current_observation
            if self.current_observation is not None \
                    and top_obs[0] != self.current_observation.name:

                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if self.observation_available(self.current_observation, end_of_next_set):

                    # If current is better or equal to top, use it
                    if self.current_observation.merit >= top_obs[1]:
                        best_obs.insert(0, self.current_observation)

            # Set the current
            self.current_observation = self.observations[top_obs[0]]
            self.current_observation.merit = top_obs[1]
        else:
            if self.current_observation is not None:
                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if end_of_next_set < common_properties['end_of_night'] and \
                        self.observation_available(self.current_observation, end_of_next_set):

                    self.logger.debug("Reusing {}".format(self.current_observation))
                    best_obs = [(self.current_observation.name, self.current_observation.merit)]
                else:
                    self.logger.warning("No valid observations found")
                    self.current_observation = None

        if not show_all and len(best_obs) > 0:
            best_obs = best_obs[0]
        return best_obs

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
        assert field_config['name'] not in self._observations.keys(), \
            self.logger.error("Cannot add duplicate field name")

        if 'exp_time' in field_config:
            field_config['exp_time'] = float(field_config['exp_time']) * u.second

        field = Field(field_config['name'], field_config['position'])

        try:
            obs = Observation(field, **field_config)
        except Exception as e:
            self.logger.warning("Skipping invalid field config: {}".format(field_config))
            self.logger.warning(e)
        else:
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
        except:
            pass

    def read_field_list(self):
        """Reads the field file and creates valid `Observations` """
        if self._fields_file is not None:
            self.logger.debug('Reading fields from file: {}'.format(self.fields_file))

            with open(self._fields_file, 'r') as yaml_string:
                self._fields_list = yaml.load(yaml_string)

        if self._fields_list is not None:
            for field_config in self._fields_list:
                self.add_observation(field_config)

##########################################################################
# Utility Methods
##########################################################################

##########################################################################
# Private Methods
##########################################################################
