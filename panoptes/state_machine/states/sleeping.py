from . import PanState


class State(PanState):

    def main(self, event_data):

        self.panoptes.say("Sleepy time. Wake me up when there are some exoplanets to find!")
