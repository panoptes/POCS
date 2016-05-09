import os
import time

from astropy.time import Time
from astropy import units as u

from ..utils import error, listify


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

        self._sleep_delay = kwargs.get('sleep_delay', 2.5)  # When looping, use this for delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)    # When checking safety, use this for delay

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

        # It's always safe to be in some states
        if event_data and event_data.event.name in ['park', 'set_park', 'clean_up', 'sleep']:
            self.logger.debug("Always safe to park")
            is_safe = True
        else:
            is_safe = self.is_safe()

        # Dummy shutdown
        if os.path.exists(self._shutdown_file):
            self.logger.warning("Found shtudown file. Returning false.")
            is_safe = False

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
        """ Transitional check for mount.

        This is used as a conditional check when transitioning between certain
        states.
        """
        return self.observatory.mount.is_tracking

    def initialize(self, event_data):
        """ """

        self.say("Initializing the system! Woohoo!")
        # self.do_check_mount_status(loop_delay=2.5)

        try:
            # Initialize the mount
            self.observatory.mount.initialize()

            # If successful, unpark and slew to home.
            if self.observatory.mount.is_initialized:
                self.observatory.mount.unpark()

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

    def sleep(self, delay=None):
        if delay is None:
            delay = self._sleep_delay

        self.logger.debug("Waiting for {} seconds".format(delay))
        time.sleep(delay)

    def wait_until_files_exist(self, filenames, transition=None, callback=None, timeout=150):
        """ Loop to wait for the existence of files on the system """
        assert filenames, self.logger.error("Filename(s) required for loop")

        filenames = listify(filenames)
        self.logger.debug("Waiting for files: {}".format(filenames))

        _files_exist = False

        # Check if all files exist
        exist = [os.path.exists(f) for f in filenames]

        if type(timeout) is not u.Quantity:
            timeout = timeout * u.second

        end_time = Time.now() + timeout
        self.logger.debug("Timeout for files: {}".format(end_time))

        while not all(exist):
            if Time.now() > end_time:
                # TODO Interrupt the camera properly

                raise error.Timeout("Timeout while waiting for files")
                break

            self.sleep()
            exist = [os.path.exists(f) for f in filenames]
        else:
            self.logger.debug("All files exist, now exiting loop")
            _files_exist = True

            if transition is not None:
                if hasattr(self, transition):
                    trans = getattr(self, transition)
                    trans()
                else:
                    self.logger.debug("Can't call transition {}".format(transition))

            if callback is not None:
                if hasattr(self, callback):
                    cb = getattr(self, callback)
                    cb()
                else:
                    self.logger.debug("Can't call callback {}".format(callback))

        return _files_exist

    def wait_until_safe(self):
        """ Waits until weather is safe """
        pass


##################################################################################################
# Private Methods
##################################################################################################
