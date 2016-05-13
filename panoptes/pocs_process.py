from . import Panoptes
from .utils import process


class PocsProcess(object):
    """ A small class that is used to control a separate process running a Panoptes instance. """

    def __init__(self, *args, **kwargs):
        self.panoptes = Panoptes()

        self.process = process.PanProcess(name="POCS_process", target_method=self.panoptes.get_ready)
