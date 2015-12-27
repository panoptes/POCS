from . import PanState


class State(PanState):

    def main(self, event_data):

        self.panoptes.say("I'm parked now. Phew.")

        # Now parked, transition to shutdown
        self.panoptes.shutdown()
