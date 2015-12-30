from astropy.time import Time
import asyncio
from functools import partial

from ..utils import error


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

##################################################################################################
# State Conditions
##################################################################################################

    def check_safety(self, event_data):
        """ Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            event_data(transitions.EventData): carries information about the event if
            called from the state machine.

        Returns:
            bool:   Latest safety flag
        """
        return self.is_safe()

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

    def on_enter_ready(self, event_data):
        """ """
        self.say("Up and ready to go!")
        self._loop.call_soon(self.schedule)

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

            future = asyncio.Future()
            asyncio.ensure_future(self._acquire_target(future))
            future.add_done_callback(self._start_tracking)

            self.say("I'm slewing over to the coordinates to track the target.")
        except Exception as e:
            self.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        finally:
            return self.observatory.mount.is_slewing

    @asyncio.coroutine
    def _acquire_target(self, future):
        self.observatory.mount.slew_to_target()

        while not self.observatory.mount.is_tracking:
            yield from asyncio.sleep(3)
        future.set_result(True)

    @asyncio.coroutine
    def _start_tracking(self, future):
        if not future.cancelled():
            self.say("I'm now tracking the target.")
            self.track()

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

##################################################################################################
# Callback Methods
##################################################################################################
