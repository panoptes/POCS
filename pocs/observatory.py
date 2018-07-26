import os
import time

from collections import OrderedDict
from datetime import datetime

from glob import glob

from astroplan import Observer
from astropy import units as u
from astropy.io import fits
from astropy import stats
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun

from pocs.base import PanBase
import pocs.dome
from pocs.images import Image
from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance
from pocs.scheduler.constraint import Altitude
from pocs.scheduler.observation import Observation
from pocs.scheduler.field import Field
from pocs import utils
from pocs.utils import current_time
from pocs.utils import error
from pocs.utils import images as img_utils
from pocs.utils import horizon as horizon_utils
from pocs.utils import list_connected_cameras
from pocs.utils import load_module


class Observatory(PanBase):

    def __init__(self, *args, **kwargs):
        """Main Observatory class

        Starts up the observatory. Reads config file, sets up location,
        dates, mount, cameras, and weather station
        """
        super().__init__(*args, **kwargs)
        self.logger.info('Initializing observatory')

        # Setup information about site location
        self.logger.info('\tSetting up location')
        self.location = None
        self.earth_location = None
        self.observer = None
        self._setup_location()

        self.logger.info('\tSetting up mount')
        self.mount = None
        self._create_mount()

        self.logger.info('\tSetting up cameras')
        self.cameras = OrderedDict()
        self._primary_camera = None
        self._create_cameras(**kwargs)

        # TODO(jamessynge): Discuss with Wilfred the serial port validation behavior
        # here compared to that for the mount.
        self.dome = pocs.dome.create_dome_from_config(self.config, logger=self.logger)

        self.logger.info('\tSetting up scheduler')
        self.scheduler = None
        self._create_scheduler()

        self.take_flat_fields = kwargs.get('take_flat_fields', True)

        self.current_offset_info = None

        self._image_dir = self.config['directories']['images']
        self.logger.info('\t Observatory initialized')

##########################################################################
# Properties
##########################################################################

    @property
    def is_dark(self):
        horizon = self.location.get('twilight_horizon', 0 * u.degree)

        t0 = current_time()
        is_dark = self.observer.is_night(t0, horizon=horizon)

        if not is_dark:
            sun_pos = self.observer.altaz(t0, target=get_sun(t0)).alt
            self.logger.debug("Sun {:.02f} > {}".format(sun_pos, horizon))

        return is_dark

    @property
    def sidereal_time(self):
        return self.observer.local_sidereal_time(current_time())

    @property
    def primary_camera(self):
        return self._primary_camera

    @primary_camera.setter
    def primary_camera(self, cam):
        cam.is_primary = True
        self._primary_camera = cam

    @property
    def current_observation(self):
        return self.scheduler.current_observation

    @current_observation.setter
    def current_observation(self, new_observation):
        self.scheduler.current_observation = new_observation

    @property
    def has_dome(self):
        return self.dome is not None

##########################################################################
# Methods
##########################################################################

    def initialize(self):
        """Initialize the observatory and connected hardware """
        self.logger.debug("Initializing mount")
        self.mount.initialize()
        if self.dome:
            self.dome.connect()

    def power_down(self):
        """Power down the observatory. Currently does nothing
        """
        self.logger.debug("Shutting down observatory")
        self.mount.disconnect()
        if self.dome:
            self.dome.disconnect()

    def status(self):
        """Get status information for various parts of the observatory
        """
        status = {}
        try:
            t = current_time()
            local_time = str(datetime.now()).split('.')[0]

            if self.mount.is_initialized:
                status['mount'] = self.mount.status()
                status['mount']['current_ha'] = self.observer.target_hour_angle(
                    t, self.mount.get_current_coordinates())
                if self.mount.has_target:
                    status['mount']['mount_target_ha'] = self.observer.target_hour_angle(
                        t, self.mount.get_target_coordinates())

            if self.dome:
                status['dome'] = self.dome.status

            if self.current_observation:
                status['observation'] = self.current_observation.status()
                status['observation']['field_ha'] = self.observer.target_hour_angle(
                    t, self.current_observation.field)

            evening_astro_time = self.observer.twilight_evening_astronomical(t, which='next')
            morning_astro_time = self.observer.twilight_morning_astronomical(t, which='next')

            status['observer'] = {
                'siderealtime': str(self.sidereal_time),
                'utctime': t,
                'localtime': local_time,
                'local_evening_astro_time': evening_astro_time,
                'local_morning_astro_time': morning_astro_time,
                'local_sun_set_time': self.observer.sun_set_time(t),
                'local_sun_rise_time': self.observer.sun_rise_time(t),
                'local_moon_alt': self.observer.moon_altaz(t).alt,
                'local_moon_illumination': self.observer.moon_illumination(t),
                'local_moon_phase': self.observer.moon_phase(t),
            }

        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get observatory status: {}".format(e))

        return status

    def get_observation(self, *args, **kwargs):
        """Gets the next observation from the scheduler

        Returns:
            observation (pocs.scheduler.observation.Observation or None): An
                an object that represents the obervation to be made

        Raises:
            error.NoObservation: If no valid observation is found
        """

        self.logger.debug("Getting observation for observatory")

        # If observation list is empty or a reread is requested
        if (self.scheduler.has_valid_observations is False or
                kwargs.get('reread_fields_file', False) or
                self.config['scheduler'].get('check_file', False)):
            self.scheduler.read_field_list()

        # This will set the `current_observation`
        self.scheduler.get_observation(*args, **kwargs)

        if self.current_observation is None:
            self.scheduler.clear_available_observations()
            raise error.NoObservation("No valid observations found")

        return self.current_observation

    def cleanup_observations(self):
        """Cleanup observation list

        Loops through the `observed_list` performing cleanup tasks. Resets
        `observed_list` when done

        """
        try:
            upload_images = self.config.get('panoptes_network', {})['image_storage']
        except KeyError:
            upload_images = False

        try:
            pan_id = self.config['pan_id']
        except KeyError:
            self.logger.warning("pan_id not set in config, can't upload images.")
            upload_images = False

        for seq_time, observation in self.scheduler.observed_list.items():
            self.logger.debug("Housekeeping for {}".format(observation))

            for cam_name, camera in self.cameras.items():
                self.logger.debug('Cleanup for camera {} [{}]'.format(
                    cam_name, camera.uid))

                dir_name = "{}/fields/{}/{}/{}/".format(
                    self.config['directories']['images'],
                    observation.field.field_name,
                    camera.uid,
                    seq_time,
                )

                img_utils.clean_observation_dir(dir_name)

                if upload_images is True:
                    self.logger.debug("Uploading directory to google cloud storage")
                    img_utils.upload_observation_dir(pan_id, dir_name)

            self.logger.debug('Cleanup finished')

        self.scheduler.reset_observed_list()

    def observe(self):
        """Take individual images for the current observation

        This method gets the current observation and takes the next
        corresponding exposure.

        """
        # Get observatory metadata
        headers = self.get_standard_headers()

        # All cameras share a similar start time
        headers['start_time'] = current_time(flatten=True)

        # List of camera events to wait for to signal exposure is done
        # processing
        camera_events = dict()

        # Take exposure with each camera
        for cam_name, camera in self.cameras.items():
            self.logger.debug("Exposing for camera: {}".format(cam_name))

            try:
                # Start the exposures
                cam_event = camera.take_observation(
                    self.current_observation, headers)

                camera_events[cam_name] = cam_event

            except Exception as e:
                self.logger.error("Problem waiting for images: {}".format(e))

        return camera_events

    def analyze_recent(self):
        """Analyze the most recent exposure

        Compares the most recent exposure to the reference exposure and determines
        the offset between the two.

        Returns:
            dict: Offset information
        """
        # Clear the offset info
        self.current_offset_info = None

        pointing_image = self.current_observation.pointing_image

        try:
            # Get the image to compare
            image_id, image_path = self.current_observation.last_exposure

            current_image = Image(image_path, location=self.earth_location)

            solve_info = current_image.solve_field()

            self.logger.debug("Solve Info: {}".format(solve_info))

            # Get the offset between the two
            self.current_offset_info = current_image.compute_offset(
                pointing_image)
            self.logger.debug('Offset Info: {}'.format(
                self.current_offset_info))

            # Store the offset information
            self.db.insert('offset_info', {
                'image_id': image_id,
                'd_ra': self.current_offset_info.delta_ra.value,
                'd_dec': self.current_offset_info.delta_dec.value,
                'magnitude': self.current_offset_info.magnitude.value,
                'unit': 'arcsec',
            })

        except error.SolveError:
            self.logger.warning("Can't solve field, skipping")
        except Exception as e:
            self.logger.warning("Problem in analyzing: {}".format(e))

        return self.current_offset_info

    def update_tracking(self):
        """Update tracking with rate adjustment.

        The `current_offset_info` contains information about how far off
        the center of the current image is from the pointing image taken
        at the start of an observation. This offset info is given in arcseconds
        for the RA and Dec.

        A mount will accept guiding adjustments in number of milliseconds
        to move in a specified direction, where the direction is either `east/west`
        for the RA axis and `north/south` for the Dec.

        Here we take the number of arcseconds that the mount is offset and,
        via the `mount.get_ms_offset`, find the number of milliseconds we
        should adjust in a given direction, one for each axis.

        Uses the `rate_adjustment` key from the `self.current_offset_info`
        """
        if self.current_offset_info is not None:
            self.logger.debug("Updating the tracking")

            # find the number of ms and direction for Dec axis
            dec_offset = self.current_offset_info.delta_dec
            dec_ms = self.mount.get_ms_offset(dec_offset, axis='dec')
            if dec_offset >= 0:
                dec_direction = 'north'
            else:
                dec_direction = 'south'

            # find the number of ms and direction for RA axis
            ra_offset = self.current_offset_info.delta_ra
            ra_ms = self.mount.get_ms_offset(ra_offset, axis='ra')
            if ra_offset >= 0:
                ra_direction = 'west'
            else:
                ra_direction = 'east'

            dec_ms = abs(dec_ms.value) * 1.5  # TODO(wtgee): Figure out why 1.5
            ra_ms = abs(ra_ms.value) * 1.

            # Ensure we don't try to move for too long
            max_time = 99999

            # Correct the Dec axis (if offset is large enough)
            if dec_ms > max_time:
                dec_ms = max_time

            if dec_ms >= 50:
                self.logger.info("Adjusting Dec: {} {:0.2f} ms {:0.2f}".format(
                    dec_direction, dec_ms, dec_offset))
                if dec_ms >= 1. and dec_ms <= max_time:
                    self.mount.query('move_ms_{}'.format(
                        dec_direction), '{:05.0f}'.format(dec_ms))

                # Adjust tracking for up to 30 seconds then fail if not done.
                start_tracking_time = current_time()
                while self.mount.is_tracking is False:
                    if (current_time() - start_tracking_time).sec * 1000 > max_time:
                        raise Exception(
                            "Trying to adjust Dec tracking for more than {} seconds".format(int(max_time / 1000)))

                    self.logger.debug("Waiting for Dec tracking adjustment")
                    time.sleep(0.1)

            # Correct the RA axis (if offset is large enough)
            if ra_ms > max_time:
                ra_ms = max_time

            if ra_ms >= 50:
                self.logger.info("Adjusting RA: {} {:0.2f} ms {:0.2f}".format(
                    ra_direction, ra_ms, ra_offset))
                if ra_ms >= 1. and ra_ms <= max_time:
                    self.mount.query('move_ms_{}'.format(
                        ra_direction), '{:05.0f}'.format(ra_ms))

                # Adjust tracking for up to 30 seconds then fail if not done.
                start_tracking_time = current_time()
                while self.mount.is_tracking is False:
                    if (current_time() - start_tracking_time).sec * 1000 > max_time:
                        raise Exception(
                            "Trying to adjust RA tracking for more than {} seconds".format(int(max_time/1000)))

                    self.logger.debug("Waiting for RA tracking adjustment")
                    time.sleep(0.1)

    def get_standard_headers(self, observation=None):
        """Get a set of standard headers

        Args:
            observation (`~pocs.scheduler.observation.Observation`, optional): The
                observation to use for header values. If None is given, use
                the `current_observation`.

        Returns:
            dict: The standard headers
        """
        if observation is None:
            observation = self.current_observation

        assert observation is not None, self.logger.warning(
            "No observation, can't get headers")

        field = observation.field

        self.logger.debug("Getting headers for : {}".format(observation))

        t0 = current_time()
        moon = get_moon(t0, self.observer.location)

        headers = {
            'airmass': self.observer.altaz(t0, field).secz.value,
            'creator': "POCSv{}".format(self.__version__),
            'elevation': self.location.get('elevation').value,
            'ha_mnt': self.observer.target_hour_angle(t0, field).value,
            'latitude': self.location.get('latitude').value,
            'longitude': self.location.get('longitude').value,
            'moon_fraction': self.observer.moon_illumination(t0),
            'moon_separation': field.coord.separation(moon).value,
            'observer': self.config.get('name', ''),
            'origin': 'Project PANOPTES',
            'tracking_rate_ra': self.mount.tracking_rate,
        }

        # Add observation metadata
        headers.update(observation.status())

        # Explicitly convert EQUINOX to float
        try:
            equinox = float(headers['equinox'].replace('J', ''))
        except BaseException:
            equinox = 2000.  # We assume J2000

        headers['equinox'] = equinox

        return headers

    def autofocus_cameras(self, camera_list=None, coarse=None):
        """
        Perform autofocus on all cameras with focus capability, or a named subset
        of these. Optionally will perform a coarse autofocus first, otherwise will
        just fine tune focus.

        Args:
            camera_list (list, optional): list containing names of cameras to autofocus.
            coarse (bool, optional): Whether to performan a coarse autofocus before
            fine tuning, default False.

        Returns:
            dict of str:threading_Event key:value pairs, containing camera names and
                corresponding Events which will be set when the camera completes autofocus.
        """
        if camera_list:
            # Have been passed a list of camera names, extract dictionary
            # containing only cameras named in the list
            cameras = {cam_name: self.cameras[
                cam_name] for cam_name in camera_list if cam_name in self.cameras.keys()}
            if cameras == {}:
                self.logger.warning(
                    "Passed a list of camera names ({}) but no matches found".format(camera_list))
        else:
            # No cameras specified, will try to autofocus all cameras from
            # self.cameras
            cameras = self.cameras

        autofocus_events = dict()

        # Start autofocus with each camera
        for cam_name, camera in cameras.items():
            self.logger.debug("Autofocusing camera: {}".format(cam_name))

            try:
                assert camera.focuser.is_connected
            except AttributeError:
                self.logger.debug(
                    'Camera {} has no focuser, skipping autofocus'.format(cam_name))
            except AssertionError:
                self.logger.debug(
                    'Camera {} focuser not connected, skipping autofocus'.format(cam_name))
            else:
                try:
                    # Start the autofocus
                    autofocus_event = camera.autofocus(coarse=coarse)
                except Exception as e:
                    self.logger.error(
                        "Problem running autofocus: {}".format(e))
                else:
                    autofocus_events[cam_name] = autofocus_event

        return autofocus_events

    def open_dome(self):
        """Open the dome, if there is one.

        Returns: False if there is a problem opening the dome,
                 else True if open (or if not exists).
        """
        if not self.dome:
            return True
        if not self.dome.connect():
            return False
        if not self.dome.is_open:
            self.logger.info('Opening dome')
        return self.dome.open()

    def close_dome(self):
        """Close the dome, if there is one.

        Returns: False if there is a problem closing the dome,
                 else True if closed (or if not exists).
        """
        if not self.dome:
            return True
        if not self.dome.connect():
            return False
        if not self.dome.is_closed:
            self.logger.info('Closed dome')
        return self.dome.close()

    def take_evening_flats(self,
                           alt=None,
                           az=None,
                           min_counts=1000,
                           max_counts=12000,
                           bias=2048,
                           max_exptime=60.,
                           camera_list=None,
                           target_adu_percentage=0.5,
                           max_num_exposures=10,
                           take_darks=False,
                           *args, **kwargs
                           ):
        """Take flat fields.

        This method will slew the mount to the given AltAz coordinates (which
        should be roughly opposite of the setting sun) and then begin the flat-field
        procedure. The first image starts with a simple 1 second exposure and
        after each image is taken the average counts are anazlyzed and the exposure
        time is adjusted to try to keep the counts close to `target_adu_percentage`
        of the `(max_counts + min_counts) - bias`.

        The next exposure time is calculated as:

        ```
            exp_time = int(previous_exp_time * (target_adu / counts) *
                       (2.0 ** (elapsed_time / 180.0)) + 0.5)
        ```

        Under- and over-exposed images are rejected. If image is saturated with
        a short exposure the method will wait 60 seconds before beginning next
        exposure.

        Optionally, the method can also take dark exposures of equal exposure
        time to each flat-field image.


        Args:
            alt (float, optional): Altitude for flats
            az (float, optional): Azimuth for flats
            min_counts (int, optional): Minimum ADU count
            max_counts (int, optional): Maximum ADU count
            bias (int, optional): Default bias for the cameras
            max_exptime (float, optional): Maximum exposure time before stopping
            camera_list (list, optional): List of cameras to use for flat-fielding
            target_adu_percentage (float, optional): Exposure time will be adjust so
                that counts are close to: target * (`min_counts` + `max_counts`). Default
                to 0.5
            max_num_exposures (int, optional): Maximum number of flats to take
            take_darks (bool, optional): If dark fields matching flat fields should be
                taken, default False.
            *args (TYPE): Description
            **kwargs (TYPE): Description
        """
        target_adu = target_adu_percentage * (min_counts + max_counts)

        image_dir = self.config['directories']['images']

        flat_obs = self._create_flat_field_observation(alt=alt, az=az)

        if camera_list is None:
            camera_list = list(self.cameras.keys())

        # Start with 1 second exposures for each camera
        exp_times = {cam_name: [1. * u.second] for cam_name in camera_list}

        # Loop until conditions are met for flat-fielding
        while True:
            self.logger.debug("Slewing to flat-field coords: {}".format(flat_obs.field))
            self.mount.set_target_coordinates(flat_obs.field)
            self.mount.slew_to_target()
            self.status()  # Seems to help with reading coords

            fits_headers = self.get_standard_headers(observation=flat_obs)

            start_time = current_time()
            fits_headers['start_time'] = utils.flatten_time(start_time)

            camera_events = dict()

            # Take the observations
            for cam_name in camera_list:

                camera = self.cameras[cam_name]
                exp_time = exp_times[cam_name][-1].value

                filename = "{}/flats/{}/{}/{}.{}".format(
                    image_dir,
                    camera.uid,
                    flat_obs.seq_time,
                    'flat_{:02d}'.format(flat_obs.current_exp),
                    camera.file_extension)

                # Take picture and get event
                camera_event = camera.take_observation(
                    flat_obs,
                    fits_headers,
                    filename=filename,
                    exp_time=exp_time
                )

                camera_events[cam_name] = {
                    'event': camera_event,
                    'filename': filename,
                }

            # Block until done exposing on all cameras
            while not all([info['event'].is_set() for info in camera_events.values()]):
                self.logger.debug('Waiting for flat-field image')
                time.sleep(1)

            # Check the counts for each image
            is_saturated = False
            for cam_name, info in camera_events.items():
                img_file = info['filename'].replace('.cr2', '.fits')
                self.logger.debug("Checking counts for {}".format(img_file))

                try:
                    data = fits.getdata(img_file)
                except FileNotFoundError:
                    data = fits.getdata(img_file.replace('.fits', '.fits.fz'))

                mean, median, stddev = stats.sigma_clipped_stats(data, iters=2)

                counts = mean - bias

                # Don't deal with negative values
                if counts <= 0:
                    counts = 10

                self.logger.debug("Counts: {}".format(counts))

                # If we are saturating then wait a bit and redo
                if counts >= max_counts:
                    self.logger.debug("Image is saturated")
                    is_saturated = True

                if counts < min_counts:
                    self.logger.debug("Counts are too low, flat should be discarded")

                elapsed_time = (current_time() - start_time).sec
                self.logger.debug("Elapsed time: {}".format(elapsed_time))

                # Get suggested exposure time
                previous_exp_time = exp_times[cam_name][-1].value

                exp_time = int(previous_exp_time * (target_adu / counts) *
                               (2.0 ** (elapsed_time / 180.0)) + 0.5)
                self.logger.debug("Suggested exp_time for {}: {}".format(cam_name, exp_time))
                exp_times[cam_name].append(exp_time * u.second)

            self.logger.debug("Checking for long exposures")
            # Stop flats if any time is greater than max
            if any([t[-1].value >= max_exptime for t in exp_times.values()]):
                self.logger.debug("Exposure times greater than max, stopping flat fields")
                break

            self.logger.debug("Checking for too many exposures")
            # Stop flats if we are going on too long
            if any([len(t) >= max_num_exposures for t in exp_times.values()]):
                self.logger.debug("Too many flats, quitting")
                break

            self.logger.debug("Checking for saturation on short exposure")
            if is_saturated and exp_times[cam_name][-1].value <= 2:
                self.logger.debug(
                    "Saturated with short exposure, waiting 30 seconds before next exposure")
                max_num_exposures += 1
                time.sleep(60)
                break

            self.logger.debug("Incrementing exposure count")
            flat_obs.current_exp += 1

        # Add a bias exposure at beginning
        for cam_name in camera_list:
            exp_times[cam_name].insert(0, 0 * u.second)

            # Record how many exposures we took
            num_exposures = len(exp_times[cam_name])

        # Reset to first exposure so we can loop through again taking darks
        flat_obs.current_exp = 0

        if take_darks:
            # Take darks
            for i in range(num_exposures):
                self.logger.debug("Slewing to dark-field coords: {}".format(flat_obs.field))
                self.mount.set_target_coordinates(flat_obs.field)
                self.mount.slew_to_target()
                self.status()

                for cam_name in camera_list:

                    camera = self.cameras[cam_name]

                    filename = "{}/darks/{}/{}/{}.{}".format(
                        image_dir,
                        camera.uid,
                        flat_obs.seq_time,
                        'dark_{:02d}'.format(flat_obs.current_exp),
                        camera.file_extension)

                    exp_time = exp_times[cam_name][i]
                    if exp_time > max_exptime:
                        continue

                    # Take picture and wait for result
                    camera_event = camera.take_observation(
                        flat_obs,
                        fits_headers,
                        filename=filename,
                        exp_time=exp_times[cam_name][i],
                        dark=True
                    )

                    camera_events[cam_name] = {
                        'event': camera_event,
                        'filename': filename,
                    }

                # Will block here until done exposing on all cameras
                while not all([info['event'].is_set() for info in camera_events.values()]):
                    self.logger.debug('Waiting for dark-field image')
                    time.sleep(1)

                flat_obs.current_exp = i


##########################################################################
# Private Methods
##########################################################################

    def _setup_location(self):
        """
        Sets up the site and location details for the observatory

        Note:
            These items are read from the 'site' config directive and include:
                * name
                * latitude
                * longitude
                * timezone
                * presseure
                * elevation
                * horizon

        """
        self.logger.debug('Setting up site details of observatory')

        try:
            config_site = self.config.get('location')

            name = config_site.get('name', 'Nameless Location')

            latitude = config_site.get('latitude')
            longitude = config_site.get('longitude')

            timezone = config_site.get('timezone')
            utc_offset = config_site.get('utc_offset')

            pressure = config_site.get('pressure', 0.680) * u.bar
            elevation = config_site.get('elevation', 0 * u.meter)
            horizon = config_site.get('horizon', 30 * u.degree)
            observe_horizon = config_site.get(
                'observe_horizon', -18 * u.degree)

            self.location = {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'timezone': timezone,
                'utc_offset': utc_offset,
                'pressure': pressure,
                'horizon': horizon,
                'observe_horizon': observe_horizon,
            }
            self.logger.debug("Location: {}".format(self.location))

            # Create an EarthLocation for the mount
            self.earth_location = EarthLocation(
                lat=latitude, lon=longitude, height=elevation)
            self.observer = Observer(
                location=self.earth_location, name=name, timezone=timezone)
        except Exception:
            raise error.PanError(msg='Bad site information')

    def _create_mount(self, mount_info=None):
        """Creates a mount object.

        Details for the creation of the mount object are held in the
        configuration file or can be passed to the method.

        This method ensures that the proper mount type is loaded.

        Args:
            mount_info (dict):  Configuration items for the mount.

        Returns:
            pocs.mount:     Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        model = mount_info.get('model')

        if 'mount' in self.config.get('simulator', []):
            model = 'simulator'
            driver = 'simulator'
            mount_info['simulator'] = True
        else:
            model = mount_info.get('brand')
            driver = mount_info.get('driver')

            # See if we have a serial connection
            try:
                port = mount_info['serial']['port']
                if port is None or len(glob(port)) == 0:
                    msg = "Mount port({}) not available. ".format(port) \
                        + "Use simulator = mount for simulator. Exiting."
                    raise error.MountNotFound(msg=msg)
            except KeyError:
                # TODO(jamessynge): We should move the driver specific validation into the driver
                # module (e.g. module.create_mount_from_config). This means we have to adjust the
                # definition of this method to return a validated but not fully initialized mount
                # driver.
                if model != 'bisque':
                    msg = "No port specified for mount in config file. " \
                        + "Use simulator = mount for simulator. Exiting."
                    raise error.MountNotFound(msg=msg)

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('pocs.mount.{}'.format(driver))

        # Make the mount include site information
        self.mount = module.Mount(location=self.earth_location)

        self.logger.debug('Mount created')

    def _create_cameras(self, **kwargs):
        """Creates a camera object(s)

        Loads the cameras via the configuration.

        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.

        Note: We are currently only operating with one camera and the `take_pic.sh`
            script automatically discovers the ports.

        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.

        Args:
            **kwargs (dict): Can pass a camera_config object that overrides the info in
                the configuration file. Can also pass `auto_detect`(bool) to try and
                automatically discover the ports.

        Returns:
            list: A list of created camera objects.

        Raises:
            error.CameraNotFound: Description
            error.PanError: Description
        """
        if kwargs.get('camera_info') is None:
            camera_info = self.config.get('cameras')

        self.logger.debug("Camera config: \n {}".format(camera_info))

        a_simulator = 'camera' in self.config.get('simulator', [])
        if a_simulator:
            self.logger.debug("Using simulator for camera")

        ports = list()

        # Lookup the connected ports if not using a simulator
        auto_detect = kwargs.get(
            'auto_detect', camera_info.get('auto_detect', False))
        if not a_simulator and auto_detect:
            self.logger.debug("Auto-detecting ports for cameras")
            try:
                ports = list_connected_cameras()
            except Exception as e:
                self.logger.warning(e)

            if len(ports) == 0:
                raise error.PanError(
                    msg="No cameras detected. Use --simulator=camera for simulator.")
            else:
                self.logger.debug("Detected Ports: {}".format(ports))

        for cam_num, camera_config in enumerate(camera_info.get('devices', [])):
            cam_name = 'Cam{:02d}'.format(cam_num)

            if not a_simulator:
                camera_model = camera_config.get('model')

                # Assign an auto-detected port. If none are left, skip
                if auto_detect:
                    try:
                        camera_port = ports.pop()
                    except IndexError:
                        self.logger.warning(
                            "No ports left for {}, skipping.".format(cam_name))
                        continue
                else:
                    try:
                        camera_port = camera_config['port']
                    except KeyError:
                        raise error.CameraNotFound(
                            msg="No port specified and auto_detect=False")

                camera_focuser = camera_config.get('focuser', None)
                camera_readout = camera_config.get('readout_time', 6.0)

            else:
                # Set up a simulated camera with fully configured simulated
                # focuser
                camera_model = 'simulator'
                camera_port = '/dev/camera/simulator'
                camera_focuser = {'model': 'simulator',
                                  'focus_port': '/dev/ttyFAKE',
                                  'initial_position': 20000,
                                  'autofocus_range': (40, 80),
                                  'autofocus_step': (10, 20),
                                  'autofocus_seconds': 0.1,
                                  'autofocus_size': 500}
                camera_readout = 0.5

            camera_set_point = camera_config.get('set_point', None)
            camera_filter = camera_config.get('filter_type', None)

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('pocs.camera.{}'.format(camera_model))
                self.logger.debug('Camera module: {}'.format(module))
            except ImportError:
                raise error.CameraNotFound(msg=camera_model)
            else:
                # Create the camera object
                cam = module.Camera(name=cam_name,
                                    model=camera_model,
                                    port=camera_port,
                                    set_point=camera_set_point,
                                    filter_type=camera_filter,
                                    focuser=camera_focuser,
                                    readout_time=camera_readout)

                is_primary = ''
                if camera_info.get('primary', '') == cam.uid:
                    self.primary_camera = cam
                    is_primary = ' [Primary]'

                self.logger.debug("Camera created: {} {} {}".format(
                    cam.name, cam.uid, is_primary))

                self.cameras[cam_name] = cam

        # If no camera was specified as primary use the first
        if self.primary_camera is None:
            self.primary_camera = self.cameras['Cam00']

        if len(self.cameras) == 0:
            raise error.CameraNotFound(
                msg="No cameras available. Exiting.", exit=True)

        self.logger.debug("Cameras created")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler', {})
        scheduler_type = scheduler_config.get('type', 'dispatch')

        # Read the targets from the file
        fields_file = scheduler_config.get('fields_file', 'simple.yaml')
        fields_path = os.path.join(self.config['directories'][
                                   'targets'], fields_file)
        self.logger.debug('Creating scheduler: {}'.format(fields_path))

        if os.path.exists(fields_path):

            try:
                # Load the required module
                module = load_module(
                    'pocs.scheduler.{}'.format(scheduler_type))

                obstruction_list = self.config['location'].get('obstructions', list())
                default_horizon = self.config['location'].get('horizon', 30 * u.degree)

                horizon_line = horizon_utils.Horizon(
                    obstructions=obstruction_list,
                    default_horizon=default_horizon.value
                )

                # Simple constraint for now
                constraints = [
                    Altitude(horizon=horizon_line),
                    MoonAvoidance(),
                    Duration(default_horizon)
                ]

                # Create the Scheduler instance
                self.scheduler = module.Scheduler(
                    self.observer, fields_file=fields_path, constraints=constraints)
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            raise error.NotFound(
                msg="Fields file does not exist: {}".format(fields_file))

    def _create_flat_field_observation(self, alt=None, az=None):
        if alt is None and az is None:
            flat_config = self.config['flat_field']['twilight']
            alt = flat_config['alt']
            az = flat_config['az']

        flat_coords = utils.altaz_to_radec(
            alt=alt, az=az, location=self.earth_location, obstime=current_time())

        self.logger.debug("Creating flat-field observation")
        field = Field('Evening Flats', flat_coords.to_string('hmsdms'))
        flat_obs = Observation(field, exp_time=1. * u.second)
        flat_obs.seq_time = utils.current_time(flatten=True)

        self.logger.debug("Flat-field observation: {}".format(flat_obs))

        return flat_obs
