from . import PanState

class State(PanState):
    def main(self):
        self.logger.info("Slewing to target")

        next_state = 'imaging'

        mount = self.panoptes.observatory.mount
        if mount.slew_to_target():
            while mount.is_slewing:
                self.sleep()
        else:
            self.logger.warning("Problem slewing. Sending back to scheduling")
            next_state = 'scheduling'


        return next_state
