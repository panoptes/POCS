from . import PanState


class State(PanState):

    def main(self):

        sleep_time = 300

        self.panoptes.say("Sleepy time. Sleeping for {} seconds".format(sleep_time))

        self.sleep(sleep_time)

        self.panoptes.initialize()
