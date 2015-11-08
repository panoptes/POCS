from astropy.time import Time

from . import PanState


class State(PanState):

    def main(self):

        next_state = 'parking'

        self.logger.info("Ok, I'm finding something good to look at...")

        while True:
            # Get the next target
            target = self.panoptes.observatory.get_target()
            self.logger.info("Got it! I'm going to check out: {}".format(target))

            # Check if target is up
            if self.panoptes.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Target: {}".format(target))

                if self.panoptes.observatory.mount.set_target_coordinates(target):
                    self.logger.debug("Mount set to target: {}".format(target))
                    next_state = 'slewing'
                else:
                    self.logger.warning("Target not properly set")
            else:
                self.logger.warning("That's weird, I have a target that is not up. Let's try to find another.")

        return next_state
