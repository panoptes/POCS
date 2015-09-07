from . import PanState

class State(PanState):
    def __init__(self, *arg, **kwargs):
        super().__init__(self, *arg, **kwargs)

    def main(self):
        panoptes.logger.info("Inside parking state")

        mount = self.panoptes.observator.mount

        # Park the mount
        mount.park()

        while mount.is_slewing:
            self.sleep()

        return 'parked'
