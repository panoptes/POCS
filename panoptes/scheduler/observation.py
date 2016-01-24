import os.path

from astropy import units as u
from astropy.time import Time

from collections import OrderedDict

from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import error
from ..utils import images


class Observation(object):

    def __init__(self, obs_config=dict(), cameras=None):
        """An object which describes a single observation.

        Each observation can have a number of different `Exposure`s based on the config settings.
        For each type of exposure ('primary' or 'secondary') there are `[type]_nexp` `Exposure`
            objects created. Each of these `Exposure`s has a list of cameras. (See `Exposure` for details)

        Example::

              - analyze: false
                primary_exptime: 300
                primary_filter: null
                primary_nexp: 3
                secondary_exptime: 300
                secondary_filter: null
                secondary_nexp: 3

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
                the YAML file, see Example.
            cameras(list[panoptes.camera]): A list of `panoptes.camera` objects to use for
                this observation.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        self.cameras = cameras

        self.logger.debug("Camears for observation: {}".format(cameras))
        self.exposures = self._create_exposures(obs_config)

        self._images_exist = False

        self.reset_exposures()

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_exposing(self):
        return self._is_exposing

    @property
    def done_exposing(self):
        """ Bool indicating whether or not any exposures are left """
        self.logger.debug("Checking if observation has exposures")

        return self._done_exposing

    @property
    def complete(self):
        return self.done_exposing


##################################################################################################
# Methods
##################################################################################################

    def get_exposure_iter(self):
        """ Yields the next exposure """

        for num, exposure in enumerate(self.exposures):
            self.logger.debug("Getting next exposure ({})".format(exposure))

            if num == len(self.exposures) - 1:
                self._done_exposing = True

            self.current_exposure = exposure
            yield exposure

    def reset_exposures(self):
        """ Resets the exposures iterator """
        self.exposure_iterator = self.get_exposure_iter()
        self._done_exposing = False
        self.current_exposure = None
        self._is_exposing = False

    def take_exposure(self):
        """ Take the next exposure """
        try:
            exposure = next(self.exposure_iterator)
            # One start_time for this round of exposures
            start_time = Time.now().isot

            img_files = []

            # Take a picture with each camera
            for cam_name, cam in self.cameras.items():
                self.logger.debug("Exposing for camera: {}".format(cam_name))
                # Start exposure
                img_file = cam.take_exposure(seconds=exposure.exptime)
                self._is_exposing = True

                obs_info = {
                    'camera_id': cam.uid,
                    'img_file': img_file,
                    'filter': exposure.filter_type,
                    'start_time': start_time,
                    'guide_image': cam.is_guide,
                }
                self.logger.debug("{}".format(obs_info))
                exposure.images[cam_name] = obs_info
                img_files.append(img_file)

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
            self._is_exposing = False
        except Exception as e:
            self.logger.warning("Can't take exposure from Observation: {}".format(e))
            self._is_exposing = False
        finally:
            return img_files

    def estimate_duration(self, overhead=0 * u.s):
        """Method to estimate the duration of a single observation.

        A quick and dirty estimation of the time it takes to execute the
        observation.  Does not take overheads such as slewing, image readout,
        or image download in to consideration.

        Args:
            overhead (astropy.units.Quantity): The overhead time for the observation in
            units which are reducible to seconds.  This is the overhead which occurs
            for each exposure.

        Returns:
            astropy.units.Quantity: The duration (with units of seconds).
        """
        duration = max([(self.primary_exptime + overhead) * self.primary_nexp,
                        (self.secondary_exptime + overhead) * self.secondary_nexp])
        self.logger.debug('Observation duration estimated as {}'.format(duration))
        return duration

##################################################################################################
# Private Methods
##################################################################################################

    def _create_exposures(self, obs_config):
        self.logger.debug("Creating exposures")

        primary_exptime = obs_config.get('primary_exptime', 120) * u.s
        primary_filter = obs_config.get('primary_filter', None)
        primary_nexp = obs_config.get('primary_nexp', 30)
        # analyze = obs_config.get('primary_analyze', False)

        primary_exposures = [self.Exposure(
            exptime=primary_exptime,
            filter_type=primary_filter,
        ) for n in range(primary_nexp)]
        self.logger.debug("Primary exposures: {}".format(primary_exposures))
        self.num_exposures = primary_nexp

        # secondary_exptime (assumes units of seconds, defaults to 120 seconds)
        # secondary_exptime = obs_config.get('secondary_exptime', 120) * u.s
        # secondary_nexp = obs_config.get('secondary_nexp', 0)
        # secondary_filter = obs_config.get('secondary_filter', None)

        # secondary_exposures = [Exposure(
        #     exptime=secondary_exptime,
        #     filter_type=secondary_filter,
        #     analyze=False,
        #     cameras=[c for c in cameras.values() if not c.is_primary],
        # ) for n in range(secondary_nexp)]

        # if secondary_nexp > primary_nexp:
        #     self.num_exposures = secondary_nexp

        # self.logger.debug("Secondary exposures: {}".format(secondary_exposures))

        return primary_exposures

##################################################################################################
# Private Class
##################################################################################################

    class Exposure(object):

        """ An individual exposure taken by an `Observation` """

        def __init__(self, exptime=120, filter_type=None):
            self.logger = get_logger(self)

            self.exptime = exptime
            self.filter_type = filter_type
            self.images = OrderedDict()
            self._images_exist = False

        @property
        def has_images(self):
            return len(self.images) > 0

        @property
        def images_exist(self):
            """ Whether or not the images indicated by `self.images` exists.

            The `images` attribute is set when the exposure starts, so this is
            effectively a test for if the exposure has ended correctly.
            """
            self._images_exist = all(os.path.exists(f) for f in self.get_images())

            if self._images_exist:
                self._is_exposing = False

            return self._images_exist

        def get_images(self):
            """ Get all the images for this exposure """
            return [f.get('img_file') for f in list(self.images.values())]

        def process_images(self, fits_headers={}, solve=True, make_pretty=False):
            """ Process the raw data images

            Args:
                fits_headers{dict, optional}:   Key/value headers for the fits file.
                solve(bool):    Plate-solve the image, defaults to True.
                make_pretty(bool):  Make a pretty image as well.
            """
            assert self.images_exist, self.logger.warning("No images to process")
            start_time = Time.now()

            self.logger.debug("Processing images: {}".format(self.images))

            for cam_name, img_info in self.images.items():
                self.logger.debug("Cam {} Info {}".format(cam_name, img_info))

                if make_pretty:
                    self.logger.debug("Making pretty image")
                    pretty_image = images.make_pretty(img_info.get('img_file'))
                    self.logger.debug("Pretty image: {}".format(pretty_image))

                if img_info.get('fits', None) is None:
                    img_name = img_info.get('img_file')
                    self.logger.debug("Observation image to convert from cr2 to fits: {}".format(img_name))

                    fits_headers['detname'] = img_info.get('camera_id', '')

                    fits_fname = images.cr2_to_fits(img_name, fits_headers=fits_headers)
                    self.images[cam_name]['fits_file'] = fits_fname
                    self.logger.debug("CR2 converted")

                    self.logger.debug("guide_image: {}".format(img_info.get('guide_image')))
                    if solve and img_info.get('guide_image', False):
                        try:
                            self.logger.debug("Plate solving field")
                            solve_info = images.get_solve_field(fits_fname)

                            self.images[cam_name]['solved'] = solve_info
                        except error.PanError as e:
                            self.logger.warning("Timeout while solving: {}".format(e))
                        except Exception as e:
                            raise error.PanError("Can't solve field: {}".format(e))
                        else:
                            self.logger.debug("Started solve")

            # End total processing time
            end_time = Time.now()
            self.logger.debug("Processing time: {}".format((end_time - start_time).to(u.s)))
