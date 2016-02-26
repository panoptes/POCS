import os
import yaml

from astroplan import Observer, get_moon
from astropy import units as u
from astropy.coordinates import SkyCoord

from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import current_time
from . import merits as merit_functions

from .target import Target


class Scheduler(Observer):

    """ Main scheduler for the PANOPTES system. Responsible for returning current targets.

    Args:
        targets_file (str): Filename of target list to load. Defaults to None.
        location (astropy.coordinates.EarthLocation): Earth location for the mount.
        cameras(list[panoptes.cameras]): The cameras to schedule

    """

    def __init__(self, targets_file=None, location=None, cameras=None, **kwargs):
        self.logger = get_logger(self)
        self.config = load_config()

        name = self.config['location'].get('name', 'Super Secret Undisclosed Location')
        horizon = self.config['location'].get('horizon', 20) * u.degree
        timezone = self.config['location'].get('timezone', 'UTC')

        # TODO: temperature, humidity, etc. from mongo

        super().__init__(name=name, location=location, timezone=timezone, **kwargs)

        if os.path.exists(targets_file):
            self.targets_file = targets_file
        else:
            self.logger.warning("Cannot load target list: {}".format(targets_file))

        self.cameras = cameras
        self.list_of_targets = None

        self.moon = get_moon(current_time(), location)

        self.horizon = horizon

    def get_target(self, weights={'observable': 1.0, 'moon_separation': 1.0}):
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
            Target: The chosen target object, defaults to None.
        """

        # Make sure we have some targets
        self.read_target_list()

        self.logger.info('Evaluating candidate targets')

        merits = []

        chosen_target = None

        for target in self.list_of_targets:
            self.logger.debug('Target: {}'.format(target.name))
            observable = False
            target_merit = 0.0
            for term in weights.keys():
                (merit_value, observable) = self.get_merit_value(term, target)

                if merit_value and observable:
                    target_merit += weights[term] * merit_value
                    self.logger.debug('\tTarget merit: {}'.format(target_merit))
                    self.logger.debug("\tTarget priority: {}".format(target.priority))
                else:
                    self.logger.debug('\t Vetoing...')
                    break

            if observable:
                merits.append((target.priority * target_merit, target))

            self.logger.debug('Target {} with priority {} has merit of {}'.format(
                              target.name, target.priority, merit_value))
        if len(merits) > 0:
            self.logger.debug(merits)
            chosen = sorted(merits, key=lambda x: x[0])[-1][1]
            self.logger.info('Chosen target is {} with priority {}'.format(
                             chosen.name, chosen.priority))
            chosen_target = chosen

        return chosen_target

##################################################################################################
# Utility Methods
##################################################################################################

    def read_target_list(self, target_list=None):
        """Reads the target database file and returns a list of target dictionaries.

        Returns:
            target_list: A list of dictionaries for input to the get_target() method.
        """
        if target_list is None:
            target_list = self.targets_file

        self.logger.debug('Reading targets from file: {}'.format(target_list))
        self.logger.debug('Cameras for targets: {}'.format(self.cameras))

        with open(target_list, 'r') as yaml_string:
            yaml_list = yaml.load(yaml_string)

        targets = []
        for target_dict in yaml_list:
            self.logger.debug("Creating target: {}".format(target_dict))
            target = Target(target_dict, cameras=self.cameras)
            targets.append(target)

        self.list_of_targets = targets

        return targets

    def get_coords_for_ha_dec(self, ha=None, dec=None, time=current_time()):
        """ Get RA/Dec coordinates for given HA/Dec for the current location

        Args:
            ha (Optional[astropy.units.degree]): Hourangle of desired position. Defaults to None
            dec (Optional[astropy.units.degree]): Declination of desired position. Defaults to None

        Returns:
            coords (astropy.coordinates.SkyCoord): A SkyCoord object representing the HA/Dec position.
        """
        assert ha is not None, self.logger.warning("Must specify ha")
        assert dec is not None, self.logger.warning("Must specify dec")

        assert isinstance(ha, u.Quantity), self.logger.warning("HA must be in degree units")
        assert isinstance(dec, u.Quantity), self.logger.warning("Dec must be in degree units")

        time.location = self.location

        lst = time.sidereal_time('apparent')
        self.logger.debug("LST: {}".format(lst))
        self.logger.debug("HA: {}".format(ha))

        ra = lst - ha
        self.logger.debug("RA: {}".format(ra))
        self.logger.debug("Dec: {}".format(dec))

        coords = SkyCoord(ra, dec)

        return coords

    def get_merit_value(self, term, target):
        """ Responsible for looking up and calling a merit value. Returns result of that call.

        Args:
            term(str):  The name of the term to be called.
            target(obj):  Target

        Returns:
        """

        # Get a reference to the method that corresponds to the weight name
        term_function = getattr(merit_functions, term)
        self.logger.debug('\tTerm Function: {}'.format(term_function))

        # Lookup actual value
        (merit_value, observable) = term_function(target, self)
        return (merit_value, observable)

##################################################################################################
# Private Methods
##################################################################################################
