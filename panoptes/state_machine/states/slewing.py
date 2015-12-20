from . import PanState


class State(PanState):

    def main(self, event_data):

        next_state = 'park'

        self.panoptes.say("I'm slewing over to the coordinates.")

        mount = self.panoptes.observatory.mount

        try:
            mount.slew_to_target()
            while mount.is_slewing:
                self.sleep()
            self.panoptes.say("I've acqured the target, let's take a picture!")
        except Exception as e:
            self.panoptes.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        else:
            if mount.is_tracking:
                next_state = 'image'
        finally:
            return next_state
