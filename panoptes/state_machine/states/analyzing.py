from . import PanState

class State(PanState):
    def main(self):
        self.logger.info("Analyzing the images.")

        next_state = 'scheduling'

        return next_state
