from . import PanState

class State(PanState):
    def main(self):

        mount = self.panoptes.observatory.mount

        mount.slew_to_home()
        while mount.is_slewing:
            self.sleep()

        # iOptrons currently need to be re-initialized so they can handle meridian.
        mount.is_initialized = False
        mount.initialize()

        mount.park()
        while not mount.is_parked:
            self.sleep()

        return 'parked'
