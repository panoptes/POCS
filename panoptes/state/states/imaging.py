"""@package panoptes.state.states
All the current PANOPTES states
"""

from panoptes.state import state

class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['analyzing']

    def run(self):
        self.logger.info("Taking a picture...")
        cam = self.observatory.cameras[0]
        cam.connect()
        cam.simple_capture_and_download(1/10)
        self.outcome = 'parking'
