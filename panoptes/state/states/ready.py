"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Ready(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['scheduling']

    def run(self):
        self.outcome = 'scheduling'
