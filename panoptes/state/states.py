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


class Parking(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['parked']

    def run(self):
        self.outcome = 'parked'


class Shutdown(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['sleeping']

    def run(self):
        self.outcome = 'sleeping'


class Sleeping(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['ready']

    def run(self):
        self.outcome = 'ready'


class Ready(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['scheduling']

    def run(self):
        self.outcome = 'scheduling'


class Scheduling(state.PanoptesState):


    def setup(self, *args, **kwargs):
        self.outcomes = ['slewing']

    def run(self):
        self.outcome = 'slewing'


class Slewing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['imaging']

    def run(self):
        self.outcome = 'imaging'


class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['analyzing']

    def run(self):
        self.outcome = 'parking'


class Analyzing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['slewing', 'scheduling']

    def run(self):
        self.outcome = 'scheduling'        

class Test_Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = []

    def run(self):
        self.outcome = 'parking'        
