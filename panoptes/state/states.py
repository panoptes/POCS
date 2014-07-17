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
        # Get the next available target
        target = self.observatory.get_target()

        try:
            self.observatory.mount.set_target_coordinates(target)
            self.outcome = 'slewing'
        except:
            self.logger.warning("Did not properly set target coordinates")
        
        self.outcome = 'slewing'


class Slewing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['imaging']

    def run(self):
        self.observatory.mount.slew_to_target()

        while self.observatory.mount.is_slewing():
            self.logger.info("Mount is slewing. Sleeping for two seconds...")
            time.sleep(2)
        
        self.outcome = 'imaging'


class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['analyzing']

    def run(self):
        self.logger.info("Taking a picture...")
        cam = self.observatory.cameras[0]
        cam.connect()
        cam.simple_capture_and_download(1/10)
        self.outcome = 'parking'


class Analyzing(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['slewing', 'scheduling']

    def run(self):
        self.outcome = 'scheduling'        