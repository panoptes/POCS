import os
import datetime
import yaml
import types
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.utils import find_current_module
import ephem

from ..utils import logger as logger
from ..utils.config import load_config
from . import merits as merits

from .target import Target

##----------------------------------------------------------------------------
##  Scheduler Class
##----------------------------------------------------------------------------
@logger.has_logger
class Scheduler(object):
    """ Main scheduler for the PANOPTES system. Responsible for returning current targets.

    Args:
        target_list_file (str): Filename of target list to load. Defaults to None.

    """
    def __init__(self, target_list_file=None):
        self.config = load_config

        if target_list_file is not None and os.path.exists(target_list_file):
            self.target_list_file = target_list_file
        else:
            self.logger.warning("Cannot load target list: {}".format(target_list_file))

        self.list_of_targets = None


    def get_target(self, observatory, weights={'observable': 1.0}):
        """Method which chooses the target to observe at the current time.

        This method examines a list of targets and performs a calculation to
        determine which is the most desirable target to observe at the current time.
        It constructs a merit value for each target which is a sum of one or more
        merit terms. The total merit value of an object is the sum of all the merit
        terms, each multiplied by a weighting factor for that term, then the sum is
        multiplied by the target's overall priority. This basic idea follows the
        general outline of the scheduler described by Denny (2004).

        Args:
            weights (dict): A dictionary whose keys are strings indicating the names
            of the merit functions to sum and whose values are the relative weights
            for each of those terms.

        Returns:
            Target: The chosen target object.
        """

        # Make sure we have some targets
        if not self.list_of_targets:
            self.read_target_list()

        self.logger.info('Evaluating candidate targets')

        merits = []

        for target in self.list_of_targets:
            self.logger.debug('Target: {}'.format(target.name))
            observable = False
            target_merit = 0.0
            for term in weights.keys():
                self.logger.debug('\tWeight: {}'.format(term))

                # Get a reference to the method that corresponds to the weight name
                # FIXME
                term_function = getattr(merits, term)
                self.logger.debug('\tTerm Function: {}'.format(term_function))

                # Lookup actual value
                (merit_value, observable) = term_function(target, observatory)
                self.logger.debug('\tMerit Value: {}'.format(merit_value))

                if merit_value and observable:
                    target_merit += weights[term]*merit_value
                    self.logger.debug('\tTarget Merit: {}'.format(target_merit))
                else:
                    self.logger.debug('\t Vetoing...')

            if observable:
                merits.append((target.priority*target_merit, target))

            self.logger.debug('Target {} with priority {} has merit of {}'.format(\
                              target.name, target.priority, merit_value))
        if len(merits) > 0:
            self.logger.debug(merits)
            chosen = sorted(merits, key=lambda x: x[0])[-1][1]
            self.logger.info('Chosen target is {} with priority {}'.format(\
                             chosen.name, chosen.priority))
            return chosen
        else:
            return None


    def read_target_list(self):
        """Reads the target database file and returns a list of target dictionaries.

        Args:
            filename (str): The YAML file to read the target information from.

        Returns:
            list: A list of dictionaries for input to the get_target() method.
        """
        self.logger.info('Reading targets from file: {}'.format(self.target_list_file))

        with open(self.target_list_file, 'r') as yaml_string:
            yaml_list = yaml.load(yaml_string)

        targets = []
        for target_dict in yaml_list:
            target = Target(target_dict)
            targets.append(target)

        self.list_of_targets = targets

        return targets

class SchedulerSimple(Scheduler):
    """ A simple scheduler that has a list of targets.

    List can be passed in at creation or read from a file. `get_target` will pop
    from the list until empty.
    """
    def __init__(self, target_file_file=None, target_list=None):
        super().__init__()
        self.target_file_file = target_file_file
        self.target_list = target_list

    def get_target(self, observatory):
        """ Gets the next target """
        assert self.target_list is not None, self.logger.warning("Target list empty for scheduler")
        return self.target_list.pop()
