from astropy.time import Time

from . import PanState

from ...utils import error


class State(PanState):

    def main(self):

        next_state = 'parking'

        self.logger.say("Ok, I'm finding something good to look at...")

        while True:
            # Get the next target
            try:
                target = self.panoptes.observatory.get_target()
                self.logger.say("Got it! I'm going to check out: {}".format(target))
            except error.NoTarget:
                self.logger.say("No valid targets found. I guess I'll go park")
                next_state = 'parking'
                break

            # Check if target is up
            if self.panoptes.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Target: {}".format(target))

                if self.panoptes.observatory.mount.set_target_coordinates(target):
                    self.logger.debug("Mount set to target: {}".format(target))
                    next_state = 'slewing'
                    break
                else:
                    self.logger.warning("Target not properly set")
            else:
                self.logger.say("That's weird, I have a target that is not up. Let's try to find another.")

        return next_state
