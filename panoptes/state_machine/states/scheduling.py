from astropy.time import Time

from . import PanState

from ...utils import error


class State(PanState):

    def main(self, event_data):

        next_state = 'park'

        self.panoptes.say("Ok, I'm finding something good to look at...")

        # Get the next target
        try:
            target = self.panoptes.observatory.get_target()
            self.panoptes.say("Got it! I'm going to check out: {}".format(target.name))
        except error.NoTarget:
            self.panoptes.say("No valid targets found. I guess I'll go park")
        else:
            # Check if target is up
            if self.panoptes.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Target: {}".format(target))

                if self.panoptes.observatory.mount.set_target_coordinates(target):
                    self.logger.debug("Mount set to target: {}".format(target))

                    # Target set, transition to slew state
                    next_state = 'acquire_target'
                else:
                    self.logger.warning("Target not properly set")
            else:
                self.panoptes.say("That's weird, I have a target that is not up. Let's try to find another.")
                next_state = 'schedule'
        finally:
            return next_state
