from . import PanState


class State(PanState):

    def main(self):

        self.panoptes.say("I'm in shut down.")

        self.panoptes.sleep()
