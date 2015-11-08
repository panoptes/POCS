from astropy.time import Time

from . import PanState


class State(PanState):

    def main(self):

        next_state = 'parking'

        self.logger.info("Ok, I'm finding something good to look at...")

        target = self.panoptes.observatory.get_target()
        self.logger.info("Got it! I'm going to check out: {}".format(target))

        mount = self.panoptes.observatory.mount

        if self.panoptes.observatory.scheduler.target_is_up(Time.now(), target):
            self.logger.debug("Target has position: {}".format(target))
            if mount.set_target_coordinates(target):
                self.logger.debug("Mount set to target: {}".format(target))
                next_state = 'slewing'
            else:
                self.logger.warning("Target not properly set")

        return next_state
