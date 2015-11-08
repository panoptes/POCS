from . import PanState


class State(PanState):

    def main(self):

        next_state = 'exit'

        self.logger.say("Looks like the sun is up, time for me to sleep.")

        # mount = self.panoptes.observatory.mount

        return next_state
