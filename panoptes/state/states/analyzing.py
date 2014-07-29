"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Analyzing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['slewing', 'scheduling']

    def run(self):
        self.outcome = 'scheduling'        