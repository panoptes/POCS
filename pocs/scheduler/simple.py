import yaml

from astropy.coordinates import SkyCoord

from ..utils.config import load_config
from ..utils import error
from .core import Scheduler

from .target import Target


class Scheduler(Scheduler):

    """ A simple scheduler that has a list of targets.

    List can be passed in at creation or read from a file. `get_target` will pop
    from the list until empty.
    """

    def __init__(self, targets_file=None, location=None):
        self.config = load_config()

        super().__init__(targets_file=targets_file, location=location)

        self._is_initialized = False

    def initialize(self):
        """ Initialize the list """
        self.read_target_list()
        self._is_initialized = True

    def get_target(self):
        """ Gets the next target """

        if not self._is_initialized:
            self.logger.debug("Target list never initialized, reading now")
            self.read_target_list()

        try:
            target = self.list_of_targets.pop()
        except Exception as e:
            raise error.NoTarget(e)

        return target

    def read_target_list(self):
        """Reads the target database file and returns a list of target dictionaries.

        Returns:
            list: A list of dictionaries for input to the get_target() method.
        """
        self.logger.debug('Reading targets from file: {}'.format(self.targets_file))

        with open(self.targets_file, 'r') as yaml_string:
            yaml_list = yaml.load(yaml_string)

        self.logger.debug("Simple target list: {}".format(yaml_list))

        targets = []
        for target_dict in yaml_list:
            target_name = target_dict.get('name')
            self.logger.debug("Looking for {}".format(target_name))

            try:
                if 'position' not in target_dict:
                    t = SkyCoord.from_name(target_name)

                    target_dict['position'] = t.to_string(style='hmsdms')
                    target_dict['frame'] = t.frame.name

                target = Target(target_dict)
            except Exception as e:
                self.logger.warning("Problem with Target: {}".format(e))
            else:
                targets.append(target)

        self.list_of_targets = targets

        return targets
