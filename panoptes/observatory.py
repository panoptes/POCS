#!/usr/bin/env python

# Import General Tools
import sys
import os
import argparse

import ephem
import datetime
import time

import importlib

from astropy import units as u
from astropy.coordinates import SkyCoord

# from panoptes import Panoptes
import panoptes
import panoptes.mount as mount
import panoptes.camera as camera
import panoptes.scheduler as scheduler

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error


@logger.has_logger
@config.has_config
class Observatory(object):

    """
    Main Observatory class
    """

    def __init__(self):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """

        self.logger.info('Initializing observatory')

       # Setup information about site location
        self.sun, self.moon = ephem.Sun(), ephem.Moon()
        self.site = self.setup_site()

        # Create default mount and cameras. Should be read in by config file
        self.mount = self.create_mount()
        self.cameras = self.create_cameras()

    def setup_site(self, start_date=ephem.now()):
        """
        Sets up the site, i.e. location details, for the observatory. These items
        are read from the 'site' config directive and include:
        * lat (latitude)
        * lon (longitude)
        * elevation
        * horizon

        Also sets up observatory.sun and observatory.moon computed from this site
        location.
        """
        self.logger.info('Seting up site details of observatory')
        site = ephem.Observer()

        if 'site' in self.config:
            config_site = self.config.get('site')

            site.lat = config_site.get('lat')
            site.lon = config_site.get('lon')
            site.elevation = float(config_site.get('elevation'))
        else:
            raise error.Error(msg='Bad site information')

        # Pressure initially set to 680.  This could be updated later.
        site.pressure = float(680)

        # Static Initializations
        site.date = start_date

        # Update the sun and moon
        self.sun.compute(site)
        self.moon.compute(site)

        return site

    def create_mount(self, mount_info=None):
        """Creates a mount object.

        Details for the creation of the mount object are held in the
        configuration file or can be passed to the method.

        This method ensures that the proper mount type is loaded.

        Note:
            This does not actually make a serial connection to the mount. To do so,
            call the 'mount.connect()' explicitly.

        Args:
            mount_info (dict): Configuration items for the mount.

        Returns:
            panoptes.mount: Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        model = mount_info.get('model')

        self.logger.info('Creating mount: {}'.format(model))

        m = None

        # Actually import the model of mount
        try:
            module = importlib.import_module('.{}'.format(model), 'panoptes.mount')
        except ImportError as err:
            raise error.NotFound(model)

        # Make the mount include site information
        m = module.Mount(config=mount_info, site=self.site)

        return m

    def create_cameras(self, camera_info=None):
        """Creates a camera object(s)

        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.

        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.

        Args:
            camera_info (dict): Configuration items for the cameras.

        Returns:
            list: A list of created camera objects.
        """
        if camera_info is None:
            camera_info = self.config.get('cameras')

        cameras = []

        for camera in camera_info:
            # Actually import the model of camera
            try:
                module = importlib.import_module('.{}'.format(camera.get('model')), 'panoptes.camera')
                cameras.append(module.Camera(config=camera))

            except ImportError as err:
                raise error.NotFound(msg=model)

        return cameras

    def start_observing(self):
        """
        Starts the observatory
        """
        # Operations Loop
        while True:
            if self.current_state == 'stop_observing':
                break

            self.query_conditions()
            next_state = states[self.current_state]()
            self.current_state = next_state

    def stop_observing(self):
        """
        Carries out any operations that are involved with shutting down.

        TBD: This might be called at the end of each night or just upon program termination
        """
        pass

    def get_target(self):

        ra = self.sun.ra
        dec = self.sun.dec

        # c = SkyCoord(ra=ra*u.radian, dec=dec*u.radian, frame='icrs')
        # c = SkyCoord('17h59m02s', '-09d46m25s', frame='icrs')
        c = SkyCoord('16h24m01s', '-39d11m34s', frame='icrs')

        return c

    def get_state(self):
        """
        Simply returns current_state
        """
        return self.current_state

    def query_conditions(self):
        # populates observatory.weather.safe
        observatory.weather.check_conditions()
        # populates observatory.camera.connected
        observatory.camera.is_connected()
        observatory.camera.is_cooling()  # populates observatory.camera.cooling
        observatory.camera.is_cooled()  # populates observatory.camera.cooled
        # populates observatory.camera.exposing
        observatory.camera.is_exposing()
        # populates observatory.mount.connected
        observatory.mount.is_connected()
        observatory.mount.is_tracking()  # populates observatory.mount.tracking
        observatory.mount.is_slewing()  # populates observatory.mount.slewing
        observatory.mount.is_parked()  # populates observatory.mount.parked

    def heartbeat(self):
        """
        Touch a file each time signaling life
        """
        self.logger.debug('Touching heartbeat file')
        with open(self.heartbeat_filename, 'w') as fileobject:
            fileobject.write(str(datetime.datetime.now()) + "\n")

    def horizon(self, alt, az):
        '''Function to evaluate whether a particular alt, az is
        above the horizon
        '''
        assert isinstance(alt, u.Quantity)
        assert isinstance(az, u.Quantity)
        if alt > 10 * u.deg:
            return True
        else:
            return False

    def is_dark(self, dark_horizon=-12):
        """
        Need to calculate day/night for site
        Initial threshold 12 deg twilight
        self.site.date = datetime.datetime.now()
        """
        self.logger.debug('Calculating is_dark.')
        self.site.date = ephem.now()
        self.sun.compute(self.site)

        self.is_dark = self.sun.alt < dark_horizon
        return self.is_dark

    def while_scheduling(self):
        '''
        The scheduling state happens while it is dark after we have requested a
        target from the scheduler, but before the target has been returned.  This
        assumes that the scheduling happens in another thread.

        From the scheduling state you can go to the parking state and the
        slewing state.

        In the scheduling state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        no
        - mount parked:         either
        - weather:              safe
        - target chosen:        no
        - test image taken:     N/A
        - target completed:     N/A
        - analysis attempted:   N/A
        - analysis in progress: N/A
        - astrometry solved:    N/A
        - levels determined:    N/A

        To transition to the slewing state, the target field must be populated, then
        the slew command is sent to the mount.

        This sets:
        - target chosen:        yes
        - test image taken:     no
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        Timeout Condition:  A reasonable timeout period for this state should be
        set.  Some advanced scheduling algorithms with many targets to consider may
        need a significant amount of time to schedule, but that reduces observing
        efficiency, so I think the timout for this state should be of order 10 sec.
        If a timeout occurs, the system should go to getting ready state.  This does
        allow a potential infinite loop scenario if scheduling is broken, because
        going to the getting ready state will usually just bouce the system back to
        scheduling, but this is okay because it does not endanger the system as it
        will still park on bad weather and at the end of the night.
        '''
        self.current_state = "scheduling"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with scheduling state.
        if self.is_dark() and \
                self.camera.connected and \
                self.camera.cooling and \
                self.camera.cooled and \
                not self.camera.exposing and \
                self.mount.connected and \
                not self.mount.slewing and \
                self.weather.safe:
            pass
        # If conditions are not consistent with scheduling state, do something.
        else:
            # If it is day, park.
            if not self.is_dark():
                self.current_state = "parking"
                self.logger.info("End of night.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")
            # If camera is not connected, connect it and go to getting ready.
            if not self.camera.connected:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera not connected.  Connecting and going to getting ready state.")
                try:
                    self.camera.connect()
                except:
                    # Failed to connect to camera
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to camera.  Parking.")
                    self.mount.park()
            # If camera is not cooling, start cooling and go to getting ready.
            if not self.camera.cooling:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera cooler is off.  Turning cooler on and going to getting ready state.")
                try:
                    self.camera.set_cooling(True)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to set cooling.  Parking.")
                    self.mount.park()
            # If camera is not cooled, go to getting ready.
            if not self.camera.cooled:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera not finished cooling.  Going to getting ready state.")
            # If camera is exposing, cancel exposure.
            if self.camera.exposing:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera is exposing.  Canceling exposure and going to getting ready state.")
                try:
                    self.camera.cancel_exposure()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to cancel exposure.  Parking.")
                    self.mount.park()
            # If mount is not connected, connect it.
            if not self.mount.connected:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Mount not connected.  Connecting and going to getting ready state.")
                try:
                    self.mount.connect()
                except:
                    # Failed to connect to mount
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to mount.  Parking.")
                    self.mount.park()
            # If mount is slewing.
            if self.mount.slewing:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Mount is slewing.  Cancelling slew and going to getting ready state.")
                try:
                    self.mount.cancel_slew()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to cancel slew.  Parking.")
                    self.mount.park()
            # If scheduling is complete
            if self.scheduler.target and self.weather.safe:
                self.logger.info(
                    "Target selected: {}".format(self.scheduler.target.name))
                self.current_state = "slewing"
                self.logger.info("Slewing telescope.")
                try:
                    self.mount.slew_to(target)
                except:
                    self.logger.critical(
                        "Slew failed.  Going to getting ready.")
                    self.current_state = "getting ready"
            # If weather is unsafe, park.
            if not self.weather.safe:
                self.current_state = "parking"
                self.logger.info("Weather is bad.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")
        return self.current_state

    def while_slewing(self):
        '''
        The slewing state happens while the system is slewing to a target position
        (note: this is distinct from the slew which happens on the way to the park
        position).

        From the slewing state, you can go to the parking state, the taking
        test image state, and the imaging state.

        In the slewing state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        yes
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     either
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        To go to the taking test image state, the slew must complete and test image
        taken is no.

        To go to the imaging state, the slew must complete and the test image taken
        must be yes.

        Completion of the slew sets:
        - mount slewing:        no

        Timeout Condition:  There should be a reasonable timeout condition on the
        slew which allows for long slews with a lot of extra time for settling and
        other considerations which may vary between mounts.  If a timeout occurs,
        the system should go to getting ready state.
        '''
        self.current_state = "slewing"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with slewing state.
        if self.mount.connected and self.mount.slewing:
            # If conditions are not consistent with scheduling state, do something.
            pass
        else:
            # If mount is no longer slewing exit to proper state
            if not self.mount.slewing and self.weather.safe:
                if not target.test_image_taken:
                    self.current_state = "taking test image"
                    self.camera.take_image(test_image=True)
                else:
                    self.current_state = "imaging"
                    self.camera.take_image(test_image=False)
            # If weather is unsafe, park.
            if not self.weather.safe:
                self.current_state = "parking"
                self.logger.info("Weather is bad.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")

        return self.current_state

    def while_taking_test_image(self):
        '''
        The taking test image state happens after one makes a large (threshold
        controlled by a setting) slew.  The system takes a short image, plate solves
        it, then determines the pointing offset and commands a correcting slew.  One
        might also check the image background levels in this test image an use them
        to set the exposure time in the science image.

        Note:  One might argue that this is so similar to the imaging state that
        they should be merged in to one state, but I think this is a useful
        distinction to make as the settings for the test image will be different
        than a science image.  For example, for a given target, only one test image
        needs to be taken, where we probably want >1 science image.  Also, we can
        use a flag to turn off this operation.

        From the taking test image state, you can go to the parking state
        and the analyzing state.

        In the taking test image state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      yes
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     no
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        To move to the analyzing state, the image must complete:

        This sets:
        - test image taken:     yes

        Timeout Condition:  A reasonable timeout should be set which allows for a
        short exposure time, plus download time and some additional overhead.  If a
        timeout occurs, ... actually I'm not sure what should happen in this case.
        Going to getting ready state will also just wait for the image to finish, so
        nothing is gained relative to having no timeout.  This suggests that we DO
        need a method to cancel an exposure which is invoked in case of a timeout,
        which is something I had specifically hoped NOT to have to create.
        '''
        self.current_state = "taking test image"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_analyzing(self):
        '''
        The analyzing state happens after one has taken an image or test image.  It
        always operates on the last image taken (whose file name should be stored
        in a variable somewhere).

        From the analyzing state, you can go to the parking state, the
        getting ready state, or the slewing state.

        In the analyzing state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     yes
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        If the analysis is successful, this sets:
        - analysis attempted:   yes
        - analysis in progress: yes
        - astrometry solved:    yes
        - levels determined:    yes

        As part of analysis step, the system compares the number of images taken of
        this target since it was chosen to the minimum number requested by scheduler
        (typically three).  If we have taken enough images of this target, we set
        target completed to yes, if not, we leave it at no.

        To move to the slewing state, target complete must be no and astrometry
        solved is yes.  The slew recenters the target based on the astrometric
        solution.

        To move to the getting ready state, the target completed must be yes.  After
        a brief stop in getting ready state (to check that all systems are still
        ok), we would presumably go back to scheduling.  The scheduler may choose to
        observe this target again.  The minimum number of images is just that, a
        minimum, it defines the smallest schedulable block.

        We need to discuss what happens when analysis fails.

        Timeout Condition:  A readonable timeout should be set.  If a timeout
        occurs, we should handle that identically to a failure of the analysis.
        '''
        self.current_state = "analyzing"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_imaging(self):
        '''
        This state happens as the camera is exposing.

        From the imaging state, you can go to the parking statee and the analyzing
        state.

        Note: as we are currently envisioning the system operations, you can not
        cancel an exposure.  The logic behind this is that if we want to go to a
        parked state, then we don't care about the image and it is easy to simply
        tag an image header with information that the exposure was interrupted by
        a park operation, so we don't care if the data gets written to disk in this
        case.  This avoids the requirement of writing complicated exposure
        cancelling code in to each camera driver.

        As a result, if the system has to park during an
        exposure (i.e. if the weather goes bad), the camera will contine to expose.
        This means that there are cases when the camera is exposing, but you are not
        in the imaging state.  There are some edge cases we need to test (especially
        in the parking and parked states) to ensure that the camera exposure
        finishes before those states are left.

        When we enter this state, we must reset the following:
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        In the imaging state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      yes
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     yes
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        Timeout Condition:  A reasonable timeout should be set is based on the
        exposure time, plus download time and some additional overhead.  If a
        timeout occurs, ... actually I'm not sure what should happen in this case.
        Going to getting ready state will also just wait for the image to finish, so
        nothing is gained relative to having no timeout.  This suggests that we DO
        need a method to cancel an exposure which is invoked in case of a timeout,
        which is something I had specifically hoped NOT to have to create.
        '''
        self.current_state = "imaging"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_parking(self):
        '''
        This is the state which is the emergency exit.  A park command has been
        issued to put the system in a safe state, but we have not yet reached the
        park position.

        From the parking state, one can only exit to the parked state.

        Timeout Condition:  There are two options I see for a timeout on the parking
        state.  The first is to not have a timeout simply because if a park has been
        commanded, then we should assume that it is critical to safety to park and
        nothing should interrupt a park command.  Alternatively, I can imagine
        wanting to resend the park command if the system does not reach park.  The
        downside to this is that we might end up in a repeating loop of issuing a
        park command to the mount over and over again in a situation where there is
        a physical obstruction to the park operation and this damages the motors.
        There might be a third alternative which is to limit the number of retries
        on the park command after timeouts.
        '''
        self.current_state = "parking"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_parked(self):
        '''
        The parked state is where the system exists at night when not observing.
        During the day, we are at the physical parked position for the mount, but
        we would be in either the shutdown or sleeping state.

        From the parked state we can go to shutdown (i.e. when the night ends), or
        we can go to getting ready (i.e. it is still night, conditions are now safe,
        and we can return to operations).

        Timeout Condition:  There is a natural timeout to this state which occurs at
        the end of the night which causes a transition to the shutdown state.
        '''
        self.current_state = "parked"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state
