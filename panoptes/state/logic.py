from astropy.time import Time
import asyncio
from functools import partial

from ..utils import error


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")
        self._state_delay = 2.0

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

        self.logger.debug("Checking safety...")

        # It's always safe to park
        if event_data.event.name == 'park':
            self.logger.debug("Always safe to park")
            is_safe = True
        else:
            is_safe = self.is_safe()

        return is_safe

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
            self.say("Since we didn't initialize, I'm going to exit.")
            self.power_down()
        else:
            self._initialized = True

        return self._initialized

    def mount_is_tracking(self, event_data):
        """ Transitional check for mount """
        return self.observatory.mount.is_tracking


##################################################################################################
# State Logic
##################################################################################################

    def on_enter_ready(self, event_data):
        """
        Once in the `ready` state our unit has been initialized successfully. The next step is to
        schedule something for the night.
        """
        self.say("Up and ready to go!")

        self.wait_until_mount('is_home', 'schedule')

    def on_enter_scheduling(self, event_data):
        """
        In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
        make sure that the target is up right now (the scheduler should have taken care of this). If
        observable, set the mount to the target and calls `slew_to_target` to begin slew.

        If no observable targets are available, `park` the unit.
        """
        self.say("Ok, I'm finding something good to look at...")

        # Get the next target
        try:
            target = self.observatory.get_target()
            self.say("Got it! I'm going to check out: {}".format(target.name))
        except error.NoTarget:
            self.say("No valid targets found. Can't schedule. Going to park.")
            self.next_state(self.park)
        else:
            # Check if target is up
            if self.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Target: {}".format(target))

                has_target = self.observatory.mount.set_target_coordinates(target)

                if has_target:
                    self.logger.debug("Mount set to target.".format(target))
                    self.next_state(self.slew_to_target)
                else:
                    self.logger.warning("Target not properly set. Parking.")
                    self.next_state(self.park)
            else:
                self.say("That's weird, I have a target that is not up. Parking.")
                self.next_state(self.park)

    def on_enter_slewing(self, event_data):
        """ Once inside the slewing state, set the mount slewing. """
        try:

            # Start the mount slewing
            self.observatory.mount.slew_to_target()

            # Wait until mount is_tracking, then transition to track state
            self.wait_until_mount('is_tracking', 'track')

            self.say("I'm slewing over to the coordinates to track the target.")
        except Exception as e:
            self.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        finally:
            return self.observatory.mount.is_slewing

    def on_enter_tracking(self, event_data):
        """ The unit is tracking the target. Proceed to observations. """
        self.say("I'm now tracking the target.")
        self.next_state(self.observe)

    def on_enter_observing(self, event_data):
        """ """
        image_time = 2.0

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
        self.say("Analyzing image...")

    def on_enter_parking(self, event_data):
        """ """
        try:
            self.say("I'm takin' it on home and then parking.")
            self.observatory.mount.home_and_park()

            self.wait_until_mount('is_parked', 'sleep')

        except Exception as e:
            self.say("Yikes. Problem in parking: {}".format(e))

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
# Convenience Methods
##################################################################################################

    def next_state(self, method, args=None):
        """ Calls the next state after a delay """
        self.logger.debug("Method: {} Args: {}".format(method, args))
        self._loop.call_later(self._state_delay, partial(method, args))

    def wait_until(self, method, transition):
        """ Waits until `position` is done, then calls `transition`

        This is a convenience method to wait for a
        """

        if self._loop.is_running():

            self.logger.debug("Creating future for {} {}".format(transition, method))
            future = asyncio.Future()
            asyncio.ensure_future(method(future))
            future.add_done_callback(partial(self._goto_state, transition))

    def wait_until_mount(self, position, transition):
        """ Small convenience method for the mount. See `wait_until` """
        self.logger.debug("Waiting until {} to call {}".format(position, transition))
        position_method = partial(self._at_position, position)
        self.wait_until(position_method, transition)


##################################################################################################
# Private Methods
##################################################################################################

    @asyncio.coroutine
    def _at_position(self, position, future):
        """ Loop until the mount is at a given `position`.

        This sets up a non-blocking loop that will be done when the mount
        `position` returns true.

        Note:
            This is to be used along with `_goto_state` in the `wait_until` method.
            See `wait_until` for details.

        Args:
            position(str):  Any one of the mount's `is_*` properties
        """
        assert position, self.logger.error("Position required for loop")

        self.logger.debug("_at_position {} {}".format(position, future))

        while not getattr(self.observatory.mount, position):
            self.logger.debug("position: {} {}".format(position, getattr(self.observatory.mount, position)))
            yield from asyncio.sleep(3)
        future.set_result(getattr(self.observatory.mount, position))

    def _goto_state(self, state, task):
        """  Create callback function for when slew is done

        Note:
            This is to be used along with `_at_position` in the `wait_until` method.
            See `wait_until` for details.

        Args:
            task(asyncio.Task): Here be dragons. See `asyncio`
            state(str):         The name of a transition method to be called.
        """
        self.logger.debug("Inside _goto_state: {}".format(state))
        if not task.cancelled() and task.result():
            goto = getattr(self, state)
            goto()
        else:
            self.logger.debug("Next state cancelled. Result from callback: {}".format(task.result()))
