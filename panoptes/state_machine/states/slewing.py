from . import PanState


class State(PanState):

    def main(self):
        self.logger.info("I'm slewing over to the coordinates.")

        next_state = 'imaging'

        mount = self.panoptes.observatory.mount
        if mount.slew_to_target():
            while mount.is_slewing:
                self.sleep()
        else:
            self.logger.warning("Wait a minute, there was a problem slewing. Sending back to scheduling.")
            next_state = 'scheduling'

        return next_state
