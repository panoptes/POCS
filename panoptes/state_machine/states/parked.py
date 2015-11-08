from . import PanState


class State(PanState):

    def main(self):

        next_state = 'shutdown'

        # mount = self.panoptes.observatory.mount

        self.logger.say("I'm parked now. Phew.")

        return next_state
