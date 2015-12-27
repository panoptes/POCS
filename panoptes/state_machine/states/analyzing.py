from . import PanState


class State(PanState):

    def main(self, event_data):
        self.panoptes.say("Analyzing the images, I'll let you know what I find.")

        self.panoptes.schedule()
