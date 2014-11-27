"""@package panoptes.state.states
All the current PANOPTES states
"""
import time

from panoptes.state import state

class Slewing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['imaging']
        self._sleep_time = 2

    def run(self):
        self.observatory.mount.slew_to_target()

        while self.observatory.mount.is_slewing():
            self.logger.debug("Mount is slewing. Sleeping for {} seconds...".format(self._sleep_time))
            time.sleep(self._sleep_time)

        self.outcome = 'imaging'
