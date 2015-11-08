from . import PanState


class State(PanState):

    def main(self):
        self.logger.say("I'm slewing over to the coordinates.")

        next_state = 'imaging'

        mount = self.panoptes.observatory.mount

        try:
            mount.slew_to_target()
            while mount.is_slewing:
                self.sleep()
        except Exception as e:
            self.logger.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
            next_state = 'parking'

        return next_state
