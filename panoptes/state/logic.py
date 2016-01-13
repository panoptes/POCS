import os

import asyncio
from functools import partial

from astropy.time import Time

from ..utils import error, listify

from collections import OrderedDict


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

        self._state_delay = kwargs.get('state_delay', 1.0)  # Small delay between State transitions
        self._sleep_delay = kwargs.get('sleep_delay', 7.0)  # When looping, use this for delay

##################################################################################################
# State Conditions
##################################################################################################

    def check_safety(self, event_data=None):
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
        if event_data and event_data.event.name == 'park':
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
                for cam in self.observatory.cameras.values():
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

##################################################################################################

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
            self.logger.info(target)
        except Exception as e:
            self.logger.error("Error in scheduling: {}".format(e))

        # Assign the _method_
        next_state = 'park'

        if target is not None:

            self.say("Got it! I'm going to check out: {}".format(target.name))

            # Check if target is up
            if self.observatory.scheduler.target_is_up(Time.now(), target):
                self.logger.debug("Setting Target coords: {}".format(target))

                has_target = self.observatory.mount.set_target_coordinates(target)

                if has_target:
                    self.logger.debug("Mount set to target.".format(target))
                    next_state = 'slew_to_target'
                else:
                    self.logger.warning("Target not properly set. Parking.")
            else:
                self.say("That's weird, I have a target that is not up. Parking.")
        else:
            self.say("No valid targets found. Can't schedule. Going to park.")

        self.goto(next_state)

##################################################################################################

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
            self.goto('park')

##################################################################################################

    def on_enter_tracking(self, event_data):
        """ The unit is tracking the target. Proceed to observations. """
        self.say("I'm now tracking the target.")

        # TODO: Correct tracking when coming from analyzing

        self.goto('observe')

##################################################################################################

    def on_enter_observing(self, event_data):
        """ """
        self.say("I'm finding exoplanets!")

        try:
            observation = self.observatory.observe()
        except Exception as e:
            self.logger.warning("Problem with imaging: {}".format(e))
            self.say("Hmm, I'm not sure what happened with that observation.")
        else:
            # Wait for file to finish to set up processing
            try:
                img_files = []
                for exposure in observation.current_exposures:
                    self.logger.debug("Exposure: {}".format(exposure))
                    img_files.extend(exposure.images)

                self.wait_until_files_exist(img_files, 'analyze')
            except Exception as e:
                self.logger.error("Problem waiting for images: {}".format(e))
                self.goto('park')

##################################################################################################

    def on_enter_analyzing(self, event_data):
        """ """
        self.say("Analyzing image...")

        next_state = 'park'
        try:
            target = self.observatory.current_target
            exposures = target.current_observation.current_exposures
            self.logger.debug("For analyzing: Target: {} \t Exposures: {}".format(target, exposures))

            reference_exposure = target.reference_exposure
            self.logger.debug("Reference exposure: {}".format(reference_exposure))

            fits_headers = {
                'target': target.name,
                'coords': target.coord.to_string(),
            }

            for exp in exposures:
                exp.process_images(fits_headers=fits_headers)

            # Analyze image for tracking error
            if reference_exposure:
                self.logger.debug("Comparing to reference image")

            # try:
            #     self.db.observations.insert({self.current_target: self.targets})
            # except:
            #     self.logger.warning("Problem inserting observation information")

            # If target has visits left, go back to observe
            if not target.done_visiting:
                next_state = 'adjust_tracking'

                # We have successfully analyzed this visit, so we go to next
            else:
                next_state = 'schedule'

        except Exception as e:
            self.logger.error("Problem in analyzing: {}".format(e))

        self.goto(next_state)

##################################################################################################

    def on_enter_parking(self, event_data):
        """ """
        try:
            self.say("I'm takin' it on home and then parking.")
            self.observatory.mount.home_and_park()

            self.say("Saving any observations")
            # if len(self.targets) > 0:
            #     for target, info in self.observatory.observed_targets.items():
            #         raw = info['observations'].get('raw', [])
            #         analyzed = info['observations'].get('analyzed', [])

            #         if len(raw) > 0:
            #             self.logger.debug("Saving {} with raw observations: {}".format(target, raw))
            #             self.db.observations.insert({target: observations})

            #         if len(analyzed) > 0:
            #             self.logger.debug("Saving {} with analyed observations: {}".format(target, observations))
            #             self.db.observations.insert({target: observations})

            self.wait_until_mount('is_parked', 'sleep')

        except Exception as e:
            self.say("Yikes. Problem in parking: {}".format(e))

##################################################################################################

    def on_enter_parked(self, event_data):
        """ """
        self.say("I'm parked now. Phew.")

##################################################################################################

    def on_enter_shutdown(self, event_data):
        """ """
        self.say("I'm in Shut Down.")

    def on_enter_sleeping(self, event_data):
        """ """
        self.say("ZZzzzz...")

##################################################################################################
# Convenience Methods
##################################################################################################

    def goto(self, method, args=None):
        """ Calls the next state after a delay

        Args:
            method(str):    The `transition` method to call, required.
        """
        if self._loop.is_running():
            # If a string was passed, look for method matching name
            if isinstance(method, str) and hasattr(self, method):
                call_method = partial(getattr(self, method))
            else:
                call_method = partial(method, args)

            self.logger.debug("Method: {} Args: {}".format(method, args))
            self._loop.call_later(self._state_delay, call_method)

    def wait_until(self, method, transition):
        """ Waits until `method` is done, then calls `transition`

        This is a convenience method to wait for a method and then transition
        """
        if self._loop.is_running():
            self.logger.debug("Creating future for {} {}".format(transition, method))

            future = asyncio.Future()
            asyncio.ensure_future(method(future))
            future.add_done_callback(partial(self._goto_state, transition))

    def wait_until_mount(self, position, transition):
        """ Small convenience method for the mount. See `wait_until` """
        if self._loop.is_running():
            self.logger.debug("Waiting until {} to call {}".format(position, transition))

            position_method = partial(self._at_position, position)
            self.wait_until(position_method, transition)

    def wait_until_files_exist(self, filenames, transition):
        """ Given a file, wait until file exists then transition """
        if self._loop.is_running():
            self.logger.debug("Waiting until {} exist to call {}".format(filenames, transition))

            try:
                future = asyncio.Future()
                asyncio.ensure_future(self._file_exists(filenames, future))
                future.add_done_callback(partial(self._goto_state, transition))
            except Exception as e:
                self.logger.error("Can't wait on file: {}".format(e))


##################################################################################################
# Private Methods
##################################################################################################

    @asyncio.coroutine
    def _at_position(self, position, future):
        """ Loop until the mount is at a given `position`.

        Non-blocking loop that finishes when mount `position` is True

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
            yield from asyncio.sleep(self._sleep_delay)
        future.set_result(getattr(self.observatory.mount, position))

    @asyncio.coroutine
    def _file_exists(self, filenames, future):
        """ Loop until file exists

        Non-blocking loop that finishes when file exists. Sets the future
        to the filename.

        Args:
            filename(str or list):  File(s) to test for existence.
        """
        assert filenames, self.logger.error("Filename required for loop")

        filenames = listify(filenames)

        self.logger.debug("_file_exists {} {}".format(filenames, future))

        # Check if all files exist
        exist = [os.path.exists(f) for f in filenames]

        # Sleep (non-blocking) until all files exist
        while not all(exist):
            self.logger.debug("{} {}".format(filenames, all(exist)))
            yield from asyncio.sleep(self._sleep_delay)
            exist = [os.path.exists(f) for f in filenames]

        self.logger.debug("All files exist, now exiting loop")
        # Now that all files exist, set result
        future.set_result(filenames)

    def _goto_state(self, state, future):
        """  Create callback function for when slew is done

        Note:
            This is to be used along with `_at_position` in the `wait_until` method.
            See `wait_until` for details.

        Args:
            future(asyncio.future): Here be dragons. See `asyncio`
            state(str):         The name of a transition method to be called.
        """
        self.logger.debug("Inside _goto_state: {}".format(state))
        if not future.cancelled():
            goto = getattr(self, state)
            goto()
        else:
            self.logger.debug("Next state cancelled. Result from callback: {}".format(future.result()))
