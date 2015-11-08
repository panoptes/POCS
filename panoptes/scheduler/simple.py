

from .core import Scheduler


class Scheduler(Scheduler):

    """ A simple scheduler that has a list of targets.

    List can be passed in at creation or read from a file. `get_target` will pop
    from the list until empty.
    """

    def __init__(self, targets_file=None, target_list=None):
        super().__init__()
        self.targets_file = targets_file
        self.target_list = target_list

    def get_target(self):
        """ Gets the next target """
        assert self.target_list is not None, self.logger.warning("Target list empty for scheduler")
        return self.target_list.pop()
