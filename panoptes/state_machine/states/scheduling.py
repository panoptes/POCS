from astropy.coordinates import SkyCoord

from . import PanState

from ...scheduler.target import Target

class State(PanState):
    def main(self):

        next_state = 'parking'

        self.logger.debug("Inside scheduling, getting target")

        target = self.panoptes.observatory.get_target()
        self.logger.debug("Target: {}".format(target))

        target_position = None

        if isinstance(target, SkyCoord):
            target_position = target

        if isinstance(target, Target):
            target_position = target.position

        if target_position is not None:
            self.logger.debug("Mount has position: {}".format(target_position))
            if self.panoptes.observatory.mount.set_target_coordinates(target_position):
                self.logger.debug("Mount set to target: {}".format(target_position))
                next_state = 'slewing'
            else:
                self.logger.warning("Target not properly set")

        return next_state
