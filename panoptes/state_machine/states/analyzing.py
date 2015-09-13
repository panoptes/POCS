from . import PanState

class State(PanState):
    def main(self):

        self.logger.info("Analyzing the images.")

        return 'scheduling'
