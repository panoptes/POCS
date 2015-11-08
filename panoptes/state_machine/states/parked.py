from . import PanState


class State(PanState):

    def main(self):

        next_state = 'shutdown'

        # mount = self.panoptes.observatory.mount

        self.logger.info("I'm parked now.")

        return next_state
