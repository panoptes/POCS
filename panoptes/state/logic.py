import os
import time

import asyncio
from functools import partial

import numpy as np
from matplotlib import pyplot as plt
from matplotlib import cm as cm
plt.style.use('ggplot')
matplotlib.use('Agg')

from astropy import units as u
from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS

from ..utils import error, listify
from ..utils import images
from ..utils import current_time

from collections import OrderedDict


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

        self._state_delay = kwargs.get('state_delay', 0.5)  # Small delay between State transitions
        self._sleep_delay = kwargs.get('sleep_delay', 2.5)  # When looping, use this for delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)    # When checking safety, use this for delay

        # This should all move to the `states.pointing` module
        point_config = self.config.get('pointing', {})
        self._max_iterations = point_config.get('max_iterations', 3)
        self._pointing_exptime = point_config.get('exptime', 30) * u.s
        self._pointing_threshold = point_config.get('threshold', 0.05) * u.deg
        self._pointing_iteration = 0

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
        if event_data and event_data.event.name in ['park', 'set_park']:
            self.logger.debug("Always safe to park")
            is_safe = True
        else:
            is_safe = self.is_safe()

        return is_safe

    def is_dark(self):
        """ Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.horizon` or 18 degrees (astronomical twilight).

        Returns:
            bool:   Is night at location

        """
        is_dark = self.observatory.is_dark

        self.logger.debug("Dark: {}".format(is_dark))
        return is_dark

    def is_safe(self):
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
        is_safe_values = dict()

        # Check if night time
        is_safe_values['is_dark'] = self.is_dark()

        # Check weather
        is_safe_values['good_weather'] = self.weather_station.is_safe()

        self.logger.debug("Safety: {}".format(is_safe_values))
        safe = all(is_safe_values.values())

        if 'weather' in self.config['simulator']:
            self.logger.debug("Weather simluator always safe")
            safe = True

        if not safe:
            self.logger.warning('System is not safe')
            self.logger.warning('{}'.format(is_safe_values))

            # Not safe so park unless we are sleeping
            if self.state not in ['sleeping', 'parked', 'parking', 'housekeeping']:
                self.park()

        self.logger.debug("Safe: {}".format(safe))
        return safe

    def mount_is_tracking(self, event_data):
        """ Transitional check for mount """
        return self.observatory.mount.is_tracking

    def initialize(self, event_data):
        """ """

        self.say("Initializing the system! Woohoo!")
        self.do_check_status(15)

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

##################################################################################################
# Convenience Methods
##################################################################################################

    def goto(self, method, args=None):
        """ Calls the next state after a delay

        Args:
            method(str):    The `transition` method to call, required.
        """
        if self._loop.is_running():
            self.logger.debug("Goto transition: {}".format(method))
            # If a string was passed, look for method matching name
            if isinstance(method, str) and hasattr(self, method):
                call_method = partial(getattr(self, method))
            else:
                call_method = partial(method, args)

            self.logger.debug("Method: {} Args: {}".format(method, args))
            self._loop.call_later(self._state_delay, call_method)
        else:
            self.logger.warning("Event loop not running, can't goto state")

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

    def wait_until_files_exist(self, filenames, transition=None, callback=None):
        """ Given a file, wait until file exists then transition """
        future = asyncio.Future()
        if self._loop.is_running():

            try:
                asyncio.ensure_future(self._file_exists(filenames, future))

                if transition is not None:
                    self.logger.debug("Waiting until {} exist to call {}".format(filenames, transition))
                    future.add_done_callback(partial(self._goto_state, transition))

                if callback is not None:
                    self.logger.debug("Waiting until {} exist to call {}".format(filenames, callback))
                    future.add_done_callback(callback)

            except Exception as e:
                self.logger.error("Can't wait on file: {}".format(e))

        return future

    def wait_until_safe(self, safe_delay=None):
        """ """
        if self._loop.is_running():
            self.logger.debug("Waiting until safe to call get_ready")

            if safe_delay is None:
                safe_delay = self._safe_delay

            wait_method = partial(self._is_safe, safe_delay=safe_delay)
            self.wait_until(wait_method, 'get_ready')

    def do_check_status(self, loop_delay=30):
        self.check_status()

        if self._loop.is_running():
            self._loop.call_later(loop_delay, partial(self.do_check_status, loop_delay))

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
            self.check_status()
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

    @asyncio.coroutine
    def _is_safe(self, future, safe_delay=None):
        if safe_delay is None:
            safe_delay = self._safe_delay

        while not self.is_safe():
            self.logger.debug("System not safe, sleeping for {}".format(safe_delay))
            yield from asyncio.sleep(self._safe_delay)

        # Now that safe, return True
        future.set_result(True)

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

    def _get_standard_headers(self, target=None):
        if target is None:
            target = self.observatory.current_target

        self.logger.debug("For analyzing: Target: {}".format(target))

        return {
            'alt-obs': self.observatory.location.get('elevation'),
            'author': self.name,
            'date-end': current_time().isot,
            'dec': target.coord.dec.value,
            'dec_nom': target.coord.dec.value,
            'epoch': float(target.coord.epoch),
            'equinox': target.coord.equinox,
            'instrument': self.name,
            'lat-obs': self.observatory.location.get('latitude').value,
            'latitude': self.observatory.location.get('latitude').value,
            'long-obs': self.observatory.location.get('longitude').value,
            'longitude': self.observatory.location.get('longitude').value,
            'object': target.name,
            'observer': self.name,
            'organization': 'Project PANOPTES',
            'ra': target.coord.ra.value,
            'ra_nom': target.coord.ra.value,
            'ra_obj': target.coord.ra.value,
            'telescope': self.name,
            'title': target.name,
        }
