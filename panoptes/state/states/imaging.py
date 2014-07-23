"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['analyzing']

    def run(self):
        self.logger.info("Taking a picture...")
        self.outcome = 'analyzing'
