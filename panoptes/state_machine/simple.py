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

##################################################################################################
# State Logic
##################################################################################################

    def on_enter_scheduling(self, event_data):
        """ """
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
                self.say("That's weird, I have a target that is not up.")

    def on_enter_slewing(self, event_data):
        """ """
        try:
            self.observatory.mount.slew_to_target()
            self.say("I'm slewing over to the coordinates to track the target.")
        except Exception as e:
            self.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        finally:
            return self.observatory.mount.is_slewing

    def on_enter_observing(self, event_data):
        """ """
        image_time = 120.0

        self.say("I'm finding exoplanets!")

        try:
            # Take a picture with each camera
            for cam in self.observatory.cameras:
                cam.take_exposure(seconds=image_time)

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
        except Exception as e:
            self.logger.warning("Problem with imaging: {}".format(e))
            self.say("Hmm, I'm not sure what happened with that picture.")

    def on_enter_analyzing(self, event_data):
        """ """
        self.say("Analying image...")

    def on_enter_parking(self, event_data):
        """ """
        try:
            self.panoptes.say("I'm takin' it on home and then parking.")
            self.panoptes.observatory.mount.home_and_park()
        except Exception as e:
            self.panoptes.say("Yikes. Problem in parking: {}".format(e))

    def on_enter_parked(self, event_data):
        """ """
        self.say("I'm parked now. Phew.")

    def on_enter_shutdown(self, event_data):
        """ """
        self.say("I'm in Shut Down.")

    def on_enter_sleeping(self, event_data):
        """ """
        self.say("ZZzzzz...")
