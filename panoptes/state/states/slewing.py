"""@package panoptes.state.states
All the current PANOPTES states
"""
import time

from panoptes.state import state

class Slewing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['imaging']

    def run(self):
        self.observatory.mount.slew_to_target()

        while self.observatory.mount.is_slewing():
            self.logger.info("Mount is slewing. Sleeping for two seconds...")
            time.sleep(2)
        
        self.outcome = 'imaging'
