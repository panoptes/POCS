from . import PanState

class State(PanState):
    def main(self):
        self.logger.info("Slewing to target")

        next_state = 'imaging'

        mount = self.panoptes.observatory.mount
        mount.slew_to_target()

        while mount.is_slewing:
            self.sleep()

        return next_state
