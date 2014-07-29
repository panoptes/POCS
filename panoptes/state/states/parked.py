"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Parked(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['shutdown', 'ready', 'quit']

        self.done = False # Dummy code to terminate

    def run(self):

        if self.done:
            self.outcome = 'quit'
        else:
            self.outcome = 'shutdown'
            self.done = True

