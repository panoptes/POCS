"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state


class Shutdown(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['sleeping']

    def run(self):
        self.outcome = 'sleeping'
