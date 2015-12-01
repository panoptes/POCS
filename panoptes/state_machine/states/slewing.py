from . import PanState


class State(PanState):

    def main(self):
        self.panoptes.say("I'm slewing over to the coordinates.")

        mount = self.panoptes.observatory.mount

        try:
            mount.slew_to_target()
            while mount.is_slewing:
                self.sleep()

            if mount.is_tracking:
                self.panoptes.image()
        except Exception as e:
            self.panoptes.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
            self.panoptes.park()
