from . import PanState

class State(PanState):
    def __init__(self, *arg, **kwargs):
        super().__init__(self, *arg, **kwargs)

    def main(self, panoptes):
        panoptes.logger.info("Inside parking state")
        return 'parked'
