from . import PanState


class State(PanState):

    def main(self):

        next_state = 'parked'

        mount = self.panoptes.observatory.mount

        try:
            if mount.is_initialized and mount.is_connected:
                self.logger.debug("Slewing mount to home then parking")
                mount.home_and_park()
        except Exception as e:
            self.logger.warning("Problem in parking: ".format(e))

        return next_state
