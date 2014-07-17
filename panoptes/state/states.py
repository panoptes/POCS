"""@package panoptes.state.states
All the current PANOPTES states
"""
from panoptes.state import state


class Parked(state.PanoptesState):

    def setup(self, *args, **kwargs):

        self.outcomes = ['shutdown', 'ready', 'quit']

    def run(self):
        self.observatory.mount.check_coordinates()

        self.outcome = 'shutdown'


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
        target_ra = "{}".format(self.observatory.sun.ra)
        target_dec = "+{}".format(self.observatory.sun.dec)

        target = (target_ra, target_dec)

        self.observatory.mount.slew_to_coordinates(target)

        self.outcome = 'imaging'


class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):

        self.outcomes = []

    def run(self):
        self.logger.info("Taking a picture...")
        cam = self.observatory.cameras[0]
        cam.connect()
        cam.simple_capture_and_download(1 / 10)

        self.outcome = 'parking'
