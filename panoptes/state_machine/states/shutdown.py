from . import PanState


class State(PanState):

    def main(self, event_data):

        self.panoptes.say("I'm in shut down.")

        self.panoptes.sleep()
