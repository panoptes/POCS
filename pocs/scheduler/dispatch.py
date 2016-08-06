import os
import yaml

from astroplan import Scheduler as BaseScheduler
from astroplan import Transitioner
from astroplan import Schedule
from astroplan import observability_table
from astropy import units as u

from pocs import PanBase

from .field import Field


class Scheduler(BaseScheduler, PanBase):

    def __init__(self, fields_file, *args, **kwargs):
        """ Default scheduler for POCS

        Loads `~pocs.scheduler.field.Field`s from a field

        Arguments:
            fields_file {str} -- Path containing the name, position, and priority of fields
        """
        assert os.path.exists(fields_file), \
            self.logger.error("Cannot load field list: {}".format(fields_file))

        PanBase.__init__(self, *args, **kwargs)

        sidereal_slew_rate = (360 * u.degree) / (86164 * u.second)
        slew_rate = sidereal_slew_rate * 0.9  # Guide rate

        transitioner = Transitioner(slew_rate=slew_rate)

        BaseScheduler.__init__(self, transitioner=transitioner, *args, **kwargs)

        self._fields_file = fields_file
        self._fields = dict()


##########################################################################
# Properties
##########################################################################

    @property
    def fields(self):
        """ Returns a dict of `~pocs.scheduler.field.Field` objects

        Note:
            `read_field_list` is called if list is None
        """
        if len(self._fields.keys()) == 0:
            self.read_field_list()

        return self._fields

    @property
    def fields_file(self):
        """ Field configuration file

        A YAML list of config items, specifying a minimum of `name` and `position`
        for the `~pocs.scheduler.field.Field`.

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

    def make_new_schedule(self):
        targets = [f.target for f in self.fields.values()]

        return observability_table(
            self.constraints,
            self.observer,
            targets,
            time_range=[self.start_time, self.end_time],
            time_grid_resolution=self.time_resolution
        )

    def add_field(self, field_config):

        if 'exp_time' in field_config:
            field_config['exp_time'] = float(field_config['exp_time']) * u.second

        try:
            field = Field(**field_config)
        except Exception as e:
            self.logger.warning("Skipping invalid field config: {}".format(field_config))
            self.logger.warning(e)
        else:
            self._fields[field.name] = field

    def remove_field(self, field_name):
        if field_name in self.fields.keys():
            del self.fields[field_name]
            self.logger.debug("Field removed: {}".format(field_name))

    def read_field_list(self):
        """ Reads the field file and populates the `fields` with valid
        `~pocs.scheduler.field.Field`s

        """
        self.logger.debug('Reading fields from file: {}'.format(self.fields_file))

        with open(self.fields_file, 'r') as yaml_string:
            field_list = yaml.load(yaml_string)

        if field_list is not None:
            for field_config in field_list:
                self.add_field(field_config)

##########################################################################
# Utility Methods
##########################################################################

##########################################################################
# Private Methods
##########################################################################
