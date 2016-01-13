import os.path

from astropy.time import Time

from collections import OrderedDict

from ..utils.logger import get_logger
from ..utils import error, listify
from ..utils.images import cr2_to_fits


class Exposure(object):

    """ An individual exposure taken by an `Observation` """

    def __init__(self, exptime=120, filter_type=None, analyze=False, cameras=[]):
        self.logger = get_logger(self)

        self.exptime = exptime
        self.filter_type = filter_type
        self.analyze = analyze
        self.cameras = listify(cameras)
        self.logger.debug("Exposure cameras: {}".format(self.cameras))

        self.images = OrderedDict()

        self._images_exist = False

        self._is_exposing = False
        self._exposed = False

    @property
    def complete(self):
        return not self.images_exist and not self.is_exposing

    @property
    def has_images(self):
        return len(self.images) > 0

    @property
    def is_exposing(self):
        return self._is_exposing

    @property
    def exposed(self):
        return self.images_exist

    @property
    def images_exist(self):
        """ Whether or not the images indicated by `self.images` exists.

        The `images` attribute is set when the exposure starts, so this is
        effectively a test for if the exposure has ended correctly.
        """
        self._exposed = all(os.path.exists(f) for f in self.images.keys())

        return self._exposed

    def process_images(self, fits_headers={}):
        if self.images_exist:
            self.logger.debug("Processing images: {}".format(self.images))
            for img_name, img_info in self.images.items():
                if img_info.get('fits', None) is None:

                    self.logger.debug("Observation image to convert from cr2 to fits: {}".format(img_name))
                    self.logger.debug("Start: {}".format(Time.now().isot))
                    hdu = cr2_to_fits(img_name, fits_headers=fits_headers)
                    self.logger.debug("End: {}".format(Time.now().isot))
                    self.logger.debug("HDU Header: {}".format(hdu.header))

                    self.images[img_name]['fits'] = hdu

    def expose(self):
        """ Takes an exposure with each camera in `cameras`.

        Loop through each camera and take the corresponding `primary` or `secondary` type.
        """

        try:
            # One start_time for this round of exposures
            start_time = Time.now().isot

            obs_info = {}

            # Take a picture with each camera
            self.logger.debug("Cameras to expose: {}".format(self.cameras))
            for cam in self.cameras:
                # Start exposure
                img_file = cam.take_exposure(seconds=self.exptime)
                self._is_exposing = True

                obs_info = {
                    'camera_id': cam.uid,
                    'img_file': img_file,
                    'analyze': cam.is_primary and self.analyze,
                    'filter': self.filter_type,
                    'start_time': start_time,
                }
                self.logger.debug("{}".format(obs_info))
                self.images[img_file] = obs_info

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
            self._is_exposing = False
        except Exception as e:
            self.logger.warning("Problem with taking exposure: {}".format(e))
            self._is_exposing = False
