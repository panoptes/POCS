from . import PanState


class State(PanState):

    def main(self):

        next_state = 'sleeping'

        self.logger.info("I'm in shut down.")

        return next_state
