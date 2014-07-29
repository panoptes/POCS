"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Sleeping(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['ready']

    def run(self):
        self.outcome = 'ready'
