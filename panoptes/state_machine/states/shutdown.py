from . import PanState


class State(PanState):

    def main(self):

        next_state = 'sleeping'

        self.panoptes.say("I'm in shut down.")

        return next_state
