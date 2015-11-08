
from ..utils.config import load_config
from .core import Scheduler


class Scheduler(Scheduler):

    """ A simple scheduler that has a list of targets.

    List can be passed in at creation or read from a file. `get_target` will pop
    from the list until empty.
    """

    def __init__(self, targets_file=None, location=None):
        self.config = load_config()

        super().__init__(targets_file=targets_file, location=location)

    def get_target(self):
        """ Gets the next target """
        if not self.list_of_targets:
            self.read_target_list()

        return self.list_of_targets.pop()
