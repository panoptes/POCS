from . import PanState

class State(PanState):
    def main(self):

        next_state = 'parked'

        mount = self.panoptes.observatory.mount

        if mount.is_initialized and mount.is_connected:
            mount.slew_to_home()
            while mount.is_slewing:
                self.logger.debug("Slewing to home...")
                self.sleep(5)

            # iOptrons currently need to be re-initialized so they can handle meridian.
            self.logger.debug("Re-initializing mount")
            mount.is_initialized = False
            mount.initialize()
            self.logger.debug("Mount re-initialized")

            self.logger.debug("Sending park command")
            mount.park()
            while not mount.is_parked:
                self.logger.debug("Slewing to park")
                self.sleep(5)

        return next_state
