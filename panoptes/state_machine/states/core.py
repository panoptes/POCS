import time
import transitions

from panoptes.utils.logger import has_logger


@has_logger
class PanState(transitions.State):

    """ Base class for PANOPTES transitions """

    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', self.__class__)

        self.panoptes = kwargs.get('panoptes', None)

        super().__init__(name=name, on_enter=['execute'])

        self._sleep_delay = 3  # seconds

    def main(self, event_data):
        msg = "Must implement `main` method inside class {}. Exiting".format(self.name)
        raise NotImplementedError(msg)
