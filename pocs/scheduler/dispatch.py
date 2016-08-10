import os
import yaml

from astroplan import observability_table
from astropy import units as u

from pocs import PanBase

from .field import Field
from .observation import Observation


class Scheduler(PanBase):

    def __init__(self, fields_file, *args, **kwargs):
        """ Default scheduler for POCS

        Loads `~pocs.scheduler.field.Field`s from a field

        Arguments:
            fields_file {str} -- Path containing the name, position, and priority of fields
        """
        PanBase.__init__(self, *args, **kwargs)

        assert os.path.exists(fields_file), \
            self.logger.error("Cannot load field list: {}".format(fields_file))

        self._fields_file = fields_file
        self._fields_list = list()
        self._observations = dict()


##########################################################################
# Properties
##########################################################################

    @property
    def observations(self):
        """ Returns a dict of `~pocs.scheduler.observation.Observation` objects
        with `~pocs.scheduler.observation.Observation.field.field_name` as the key

        Note:
            `read_field_list` is called if list is None
        """
        if len(self._observations.keys()) == 0:
            self.read_field_list()

        return self._observations

    @property
    def fields_file(self):
        """ Field configuration file

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

    def get_observability_table(self):
        targets = [f for f in self.fields.values()]

        return observability_table(
            self.constraints,
            self.observer,
            targets,
            time_range=[self.start_time, self.end_time],
            time_grid_resolution=self.time_resolution
        )

    def add_observation(self, field_config):

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
        if field_name in self._observations.keys():
            try:
                obs = self._observations[field_name]
                del self._observations[field_name]
                self.logger.debug("Observation removed: {}".format(obs))
            except:
                pass

    def read_field_list(self):
        """ Reads the field file and creates valid `~pocs.scheduler.observation.Observations` """
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
