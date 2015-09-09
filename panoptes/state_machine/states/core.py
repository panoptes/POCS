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

    def main(self):
        assert self.panoptes is not None
        msg = "Must implement `main` method inside class {}".format(self.name)
        # self.panoptes.logger.warning(msg)
        return 'exit'

    def sleep(self, seconds=None):
        """ sleep for `seconds` or `_sleep_delay` seconds """
        assert self.panoptes is not None

        if seconds is None:
            seconds = self._sleep_delay

        self.panoptes.logger.info("Sleeping {} for {} seconds".format(self.name, seconds))
        time.sleep(seconds)
