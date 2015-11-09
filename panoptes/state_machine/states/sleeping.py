from . import PanState


class State(PanState):

    def main(self):

        next_state = 'initializing'

        sleep_time = 300

        self.panoptes.say("Looks like the sun is up, time for me to sleep. Sleeping for {} seconds".format(sleep_time))

        self.sleep(sleep_time)

        # mount = self.panoptes.observatory.mount

        return next_state
