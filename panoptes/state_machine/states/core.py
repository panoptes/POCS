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
        msg = "Must implement `main` method inside class {}. Exiting".format(self.name)
        self.panoptes.logger.warning(msg)
        return 'exit'

    def sleep(self, seconds=None):
        """ sleep for `seconds` or `_sleep_delay` seconds

        This puts the state into a loop that is responsive to outside  messages.

        Args:
            seconds(float): Seconds to sleep for, defaults to `_sleep_delay`.
        """
        assert self.panoptes is not None

        if seconds is None:
            seconds = self._sleep_delay

        self.panoptes.say("Bedtime. Let me sleep for at least {} seconds".format(seconds))

        if seconds > 10:
            step_time = seconds / 4
            while seconds:
                seconds = seconds - step_time

                # NOTE: DO SOMETHING RESPONSIVE HERE
                self.panoptes.say("I'm still sleeping. Another {}...".format(seconds))

                time.sleep(step_time)
        else:
            time.sleep(seconds)
