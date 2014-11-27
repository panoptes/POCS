"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Parking(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['parked']

    def run(self):
        self.logger.debug("In Parking, going to Parked")
        self.observatory.mount.slew_to_park()
        self.outcome = 'parked'
