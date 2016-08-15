import os
import yaml

from astropy import units as u
from astroplan import Observer

from ..utils import current_time
from .. import PanBase

from .field import Field
from .observation import Observation


class Scheduler(PanBase):

    def __init__(self, fields_file, observer, constraints=list(), *args, **kwargs):
        """Loads `~pocs.scheduler.field.Field`s from a field

        Args:
            fields_file (str): YAML file containing field parameters
            constraints (list, optional): List of `Constraints` to apply to each
                observation
            *args: Arguments to be passed to `PanBase`
            **kwargs: Keyword args to be passed to `PanBase`
        """
        PanBase.__init__(self, *args, **kwargs)

        assert os.path.exists(fields_file), \
            self.logger.error("Cannot load field list: {}".format(fields_file))

        assert isinstance(observer, Observer)

        self._fields_file = fields_file
        self._fields_list = list()
        self._observations = dict()

        self.observer = observer

        self.constraints = constraints


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
    def fields_file(self):
        """Field configuration file

        A YAML list of config items, specifying a minimum of `name` and `position`
        for the `~pocs.scheduler.field.Field`. `Observation`s will be built from
        the list of fields.

        A file will be read by `~pocs.scheduler.priority.read_field_list` upon
        being set.

        """
        return self._fields_file

    @fields_file.setter
    def fields_file(self, new_file):
        self._fields_file = new_file
        self.read_field_list()


##########################################################################
# Methods
##########################################################################

    def get_observation(self, time=None, show_all=False):
        if time is None:
            time = current_time()

        valid_obs = {obs: 1.0 for obs in self.observations}

        common_properties = {
            'sunrise': self.observer.tonight(time=time, horizon=30 * u.degree)[-1],
        }

        for constraint in self.constraints:
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

        # Sort the list by highest score (reverse puts in correct order)
        best_obs = sorted(valid_obs.items(), key=lambda x: x[1])[::-1]

        if not show_all:
            best_obs = best_obs[0]

        return best_obs

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
        if field_name in self._observations.keys():
            try:
                obs = self._observations[field_name]
                del self._observations[field_name]
                self.logger.debug("Observation removed: {}".format(obs))
            except:
                pass

    def read_field_list(self):
        """Reads the field file and creates valid `Observations` """
        self.logger.debug('Reading fields from file: {}'.format(self.fields_file))

        with open(self.fields_file, 'r') as yaml_string:
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
