import os
import time

import asyncio
from functools import partial

import numpy as np
import seaborn
from matplotlib import pyplot as plt
from matplotlib import cm as cm

from astropy import units as u
from astropy.time import Time
from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS

from ..utils import error, listify
from ..utils import images

from collections import OrderedDict


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

        self._state_delay = kwargs.get('state_delay', 1.0)  # Small delay between State transitions
        self._sleep_delay = kwargs.get('sleep_delay', 7.0)  # When looping, use this for delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)    # When checking safety, use this for delay

        point_config = self.config.get('pointing', {})
        self._max_iterations = point_config.get('max_iterations', 3)
        self._pointing_exptime = point_config.get('exptime', 30) * u.s
        self._pointing_threshold = point_config.get('threshold', 0.10) * u.deg
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
        is_safe = dict()

        # Check if night time
        is_safe['is_dark'] = self.is_dark()

        # Check weather
        is_safe['good_weather'] = self.weather_station.is_safe()

        safe = all(is_safe.values())

        if 'weather' in self.config['simulator']:
            self.logger.debug("Weather simluator always safe")
            safe = True

        if not safe:
            self.logger.warning('System is not safe')
            self.logger.warning('{}'.format(is_safe))

            # Not safe so park unless we are sleeping
            if self.state not in ['sleeping', 'parked', 'parking']:
                self.park()

        return safe

    def mount_is_tracking(self, event_data):
        """ Transitional check for mount """
        return self.observatory.mount.is_tracking

    def initialize(self, event_data):
        """ """

        self.say("Initializing the system! Woohoo!")

        try:
            # Initialize the mount
            self.observatory.mount.initialize()

            # If successful, unpark and slew to home.
            if self.observatory.mount.is_initialized:
                self.observatory.mount.unpark()

                self.do_check_status()

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
            self.wait_until_mount('is_tracking', 'adjust_pointing')
            self.say("I'm slewing over to the coordinates to track the target.")

        except Exception as e:
            self.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
            self.goto('park')

##################################################################################################

    def on_enter_pointing(self, event_data):
        """ Adjust pointing.

        * Take 60 second exposure
        * Call `sync_coordinates`
            * Plate-solve
            * Get pointing error
            * If within `_pointing_threshold`
                * goto tracking
            * Else
                * set set mount target coords to center RA/Dec
                * sync mount coords
                * slew to target
        """

        try:
            self.say("Taking guide picture.")

            guide_camera = self.observatory.get_guide_camera()

            path = self.observatory.construct_filename().split('/')
            directory = path[:-2]
            fn = path[-1]

            guide_image = guide_camera.take_exposure(seconds=self._pointing_exptime, filename=fn, directory=directory)
            self.logger.debug("Waiting for guide image: {}".format(guide_image))

            try:
                future = self.wait_until_files_exist(guide_image)

                self.logger.debug("Adding callback for guide image")
                future.add_done_callback(partial(self.sync_coordinates))
            except Exception as e:
                self.logger.error("Problem waiting for images: {}".format(e))
                self.goto('park')

        except Exception as e:
            self.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
            self.goto('park')

    def sync_coordinates(self, future):
        """ Adjusts pointing error from the most recent image.

        Receives a future from an asyncio call (e.g.,`wait_until_files_exist`) that contains
        filename of recent image. Uses utility function to return pointing error. If the error
        is off by some threshold, sync the coordinates to the center and reacquire the target.
        Iterate on process until threshold is met then start tracking.

        Parameters
        ----------
        future : {asyncio.Future}
            Future from returned from asyncio call, `.get_result` contains filename of image.

        Returns
        -------
        u.Quantity
            The separation between the center of the solved image and the target.
        """
        self.logger.debug("Getting pointing error")
        self.say("Ok, I've got the guide picture, let's see how close we are")

        separation = 0 * u.deg
        self.logger.debug("Default separation: {}".format(separation))

        if future.done() and not future.cancelled():
            self.logger.debug("Task completed successfully, getting image name")

            fname = future.result()[0]

            self.logger.debug("Processing image: {}".format(fname))

            target = self.observatory.current_target

            fits_headers = self._get_standard_headers(target=target)
            self.logger.debug("Guide headers: {}".format(fits_headers))

            kwargs = {}
            if 'ra_center' in target._guide_wcsinfo:
                kwargs['ra'] = target._guide_wcsinfo['ra_center'].value
            if 'dec_center' in target._guide_wcsinfo:
                kwargs['dec'] = target._guide_wcsinfo['dec_center'].value
            if 'fieldw' in target._guide_wcsinfo:
                kwargs['radius'] = target._guide_wcsinfo['fieldw'].value

            self.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
            processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)
            # self.logger.debug("Processed info: {}".format(processed_info))

            # Use the solve file
            fits_fname = processed_info.get('solved_fits_file', None)

            if os.path.exists(fits_fname):
                # Get the WCS info and the HEADER info
                self.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

                wcs_info = images.get_wcsinfo(fits_fname)
                self.logger.debug("WCS Info: {}".format(wcs_info))

                # Save guide wcsinfo to use for future solves
                target._guide_wcsinfo = wcs_info

                target = None
                with fits.open(fits_fname) as hdulist:
                    hdu = hdulist[0]
                    # self.logger.debug("FITS Headers: {}".format(hdu.header))

                    target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
                    self.logger.debug("Target coords: {}".format(target))

                # Create two coordinates
                center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
                self.logger.debug("Center coords: {}".format(center))

                if target is not None:
                    separation = center.separation(target)
        else:
            self.logger.debug("Future cancelled. Result from callback: {}".format(future.result()))

        self.logger.debug("Separation: {}".format(separation))
        if separation < self._pointing_threshold:
            self.say("I'm pretty close to the target, starting track.")
            self.goto('track')
        elif self._pointing_iteration >= self._max_iterations:
            self.say("I've tried to get closer to the target but can't. I'll just observe where I am.")
            self.goto('track')
        else:
            self.say("I'm still a bit away from the target so I'm going to try and get a bit closer.")

            self._pointing_iteration = self._pointing_iteration + 1

            # Set the target to center
            has_target = self.observatory.mount.set_target_coordinates(center)

            if has_target:
                # Tell the mount we are at the target, which is the center
                self.observatory.mount.serial_query('calibrate_mount')
                self.say("Syncing with the latest image...")

                # Now set back to target
                if target is not None:
                    self.observatory.mount.set_target_coordinates(target)

            self.goto('slew_to_target')


##################################################################################################

    def on_enter_tracking(self, event_data):
        """ The unit is tracking the target. Proceed to observations. """
        self.say("I'm now tracking the target.")

        # Get the delay for the RA and Dec and adjust mount accordingly.
        for d in ['ra', 'dec']:
            key = '{}_ms_offset'.format(d)
            if key in target._offset_info:

                # Add some offset to the offset
                ms_offset = target._offset_info.get(key, 0 * u.ms).value
                self.logger.debug("{} {}".format(key, ms_offset))

                # Only adjust a reasonable offset
                if abs(ms_offset) < 10.0:
                    continue

                # One-fourth of time. FIXME
                processing_time_delay = (ms_offset / 4.0)
                self.logger.debug("Processing time delay: {}".format(processing_time_delay))

                ms_offset = ms_offset + processing_time_delay
                self.logger.debug("Total offset: {}".format(ms_offset))

                # This hurts me to look at
                if d == 'ra':
                    if ms_offset > 0:
                        direction = 'west'
                    else:
                        ms_offset = abs(ms_offset)
                        direction = 'east'
                elif d == 'dec':
                    if ms_offset > 0:
                        direction = 'south'
                    else:
                        ms_offset = abs(ms_offset)
                        direction = 'north'

                self.say("I'm adjusting the tracking by just a bit to the {}.".format(direction))

                move_dir = 'move_ms_{}'.format(direction)
                move_ms = "{:05.0f}".format(ms_offset)
                self.logger.debug("Adjusting tracking by {} to direction {}".format(move_ms, move_dir))

                self.observatory.mount.serial_query(move_dir, move_ms)

                # The above is a non-blocking command but if we issue the next command (via the for loop)
                # then it will override the above, so we manually block for one second
                # time.sleep(ms_offset / 1000)

        # Reset offset_info
        target._offset_info = {}

        self.goto('observe')

##################################################################################################

    def on_enter_observing(self, event_data):
        """ """
        self.say("I'm finding exoplanets!")

        try:
            img_files = self.observatory.observe()
        except Exception as e:
            self.logger.warning("Problem with imaging: {}".format(e))
            self.say("Hmm, I'm not sure what happened with that exposure.")
        else:
            # Wait for files to exist to finish to set up processing
            try:
                self.wait_until_files_exist(img_files, transition='analyze')
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
            self.logger.debug("For analyzing: Target: {}".format(target))

            observation = target.current_visit
            self.logger.debug("For analyzing: Observation: {}".format(observation))

            exposure = observation.current_exposure
            self.logger.debug("For analyzing: Exposure: {}".format(exposure))

            # Get the standard FITS headers. Includes information about target
            fits_headers = self._get_standard_headers(target=target)
            fits_headers['title'] = target.name

            try:
                kwargs = {}
                if 'ra_center' in target._guide_wcsinfo:
                    kwargs['ra'] = target._guide_wcsinfo['ra_center'].value
                if 'dec_center' in target._guide_wcsinfo:
                    kwargs['dec'] = target._guide_wcsinfo['dec_center'].value
                if 'fieldw' in target._guide_wcsinfo:
                    kwargs['radius'] = target._guide_wcsinfo['fieldw'].value

                # Process the raw images (just makes a pretty right now - we solved above and offset below)
                self.logger.debug("Starting image processing")
                exposure.process_images(fits_headers=fits_headers, solve=False, **kwargs)
            except Exception as e:
                self.logger.warning("Problem analyzing: {}".format(e))

            # Should be one Guide image per exposure set corresponding to the `primary` camera
            # current_img = exposure.get_guide_image_info()

            # Analyze image for tracking error
            if target._previous_center is not None:
                self.logger.debug("Getting offset from guide")

                target._offset_info = target.get_image_offset(exposure)

                self.logger.debug("Offset information: {}".format(target._offset_info))
                self.logger.debug(
                    "Δ RA/Dec [pixel]: {} {}".format(target._offset_info['delta_ra'], target._offset_info['delta_dec']))
            else:
                # If no guide data, this is first image of set
                target._previous_center = images.crop_data(
                    images.read_image_data(current_img['img_file']), box_width=500)

        except Exception as e:
            self.logger.error("Problem in analyzing: {}".format(e))

        # If target has visits left, go back to observe
        if not observation.complete:
            # We have successfully analyzed this visit, so we go to next
            next_state = 'adjust_tracking'
        else:
            next_state = 'schedule'

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

            self.wait_until_mount('is_parked', 'set_park')

        except Exception as e:
            self.say("Yikes. Problem in parking: {}".format(e))

##################################################################################################

    def on_enter_parked(self, event_data):
        """ """
        self.say("I'm parked now. Phew.")

        next_state = 'sleep'

        # Assume dark (we still check weather)
        if self.is_dark():
            # Assume bad weather so wait
            if not self.weather_station.is_safe():
                next_state = 'wait'
            else:
                self.say("Weather is good and it is dark. Something must have gone wrong. Sleeping")
        else:
            self.say("Another successful night! I'm going to get some sleep!")

        # Either wait until safe or goto next state (sleeping)
        if next_state == 'wait':
            self.wait_until_safe()
        else:
            self.goto(next_state)

##################################################################################################

    def on_enter_housekeeping(self, event_data):
        """ """
        self.say("Let's record the data and do some cleanup for the night!")

##################################################################################################

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
            'date-end': Time.now().isot,
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
