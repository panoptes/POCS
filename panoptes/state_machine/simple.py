from astropy.time import Time

from ..utils.logger import has_logger
from ..utils import error


@has_logger
class PanStateLogic():

    """ The enter and exit logic for each state. """

##################################################################################################
# State Conditions
##################################################################################################

    def initialize(self, event_data):
        """ """

        self.say("Getting ready! Woohoo!")

        try:
            # Initialize the mount
            self.observatory.mount.initialize()

            # If successful, unpark and slew to home.
            if self.observatory.mount.is_initialized:
                self.observatory.mount.unpark()

                # Slew to home
                self.observatory.mount.slew_to_home()

                # Initialize each of the cameras while slewing
                for cam in self.observatory.cameras:
                    cam.connect()
            else:
                raise error.InvalidMountCommand("Mount not initialized")

        except Exception as e:
            self.say("Oh wait. There was a problem initializing: {}".format(e))
        else:
            self._initialized = True

        return self._initialized

    def get_target(self, event_data):
        """ """
        has_target = False
        self.say("Ok, I'm finding something good to look at...")

        # Get the next target
        try:
            target = self.observatory.get_target()
            self.say("Got it! I'm going to check out: {}".format(target.name))
        except error.NoTarget:
            self.say("No valid targets found. Can't schedule")
        else:
            # Check if target is up
            if self.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Target: {}".format(target))

                has_target = self.observatory.mount.set_target_coordinates(target)

                if has_target:
                    self.logger.debug("Mount set to target: {}".format(target))
                else:
                    self.logger.warning("Target not properly set")
            else:
                self.say("That's weird, I have a target that is not up. Let's try to find another.")
        finally:
            return has_target
