import json
import os
import time

from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils import DAOStarFinder
from string import Template

from .. import PanBase
from ..utils import error
from ..utils.theskyx import TheSkyX


class Guide(PanBase):

    def __init__(self, bin_size=None, image_path=None, template_dir=None, *args, **kwargs):
        """"""
        super().__init__(*args, **kwargs)
        self.theskyx = TheSkyX()

        if template_dir is None:
            template_dir = self.config['guider']['template_dir']

        if template_dir.startswith('/') is False:
            template_dir = os.path.join(os.environ['POCS'], template_dir)

        assert os.path.exists(template_dir), self.logger.warning("Bisque guider requires a template directory")

        self.template_dir = template_dir

        if bin_size is None:
            bin_size = self.config['guider']['bin_size']

        self.bin_size = bin_size

        if image_path is None:
            image_path = self.config['guider']['image_path']

        self.image_path = None

        self._is_connected = False
        self._is_guiding = False

    @property
    def is_connected(self):
        """ Camera connected property

        Returns:
            bool: Indicates if camera has been connected
        """
        return self._is_connected

    @property
    def is_guiding(self):
        """ Camera guiding property

        Returns:
            bool: Indicates if camera is currently autoguiding
        """
        return self._is_guiding

    @property
    def state(self):
        """ Get state of the camera

        State can be one of the following:
            Idle
            Exposing
            Exposing Series
            Focus
            Moving
            Autoguiding
            Calibrating
            Exposing Color
            Autofocus
            Autofocus

        Returns:
            str: State of camera
        """
        state = 'Unknown'
        if self.is_connected:
            response = self.query('guider/get_state.js')
            if response['success']:
                state = response['msg']

        return state

    def connect(self):
        """ Connect to camera

        Returns:
            bool: Indicates if camera connection was successful
        """
        if not self.is_connected:
            self.logger.debug("Connecting to guide camera")
            response = self.query('guider/connect.js')
            self._is_connected = response['success']

        return self.is_connected

    def disconnect(self):
        """ Disconnect from camera

        Returns:
            bool: Indicates if disconnection was successful
        """
        if self.is_connected:
            self.logger.debug("Disconnecting guide camera")
            response = self.query('guider/disconnect.js')
            self._is_connected = not response['success']

        return not self.is_connected

    def reset(self):
        """ Reset camera by disconnecting and then connecting again

        Returns:
            bool: Indicates if reset was successful and camera is connected
        """
        self.logger.debug("Resetting guide camera")
        response = self.query('guider/reset.js')
        self._is_connected = response['success']

        return self.is_connected

    def start_guiding(self, bin_size=None, exp_time=None):
        """ Start autoguiding

        Returns:
            bool: Indicates if camera is guiding
        """
        if self.is_connected:
            if not self.is_guiding:

                if bin_size is None:
                    bin_size = self.bin_size

                response = self.query('guider/start_guiding.js', {'bin': bin_size, 'exptime': exp_time})
                self._is_guiding = response['success']

        return self.is_guiding

    def stop_guiding(self):
        """ Stop autoguiding

        Returns:
            bool: True value indciates guiding has successfully stopped
        """
        if self.is_connected:
            if self.is_guiding:

                response = self.query('guider/stop_guiding.js')
                self._is_guiding = not response['success']

        return not self.is_guiding

    def set_guide_position(self, bin_size=None, x=None, y=None):
        """ Sets the guide position on the guider CCD

        Args:
            bin_size (int, optional): Binning size defaults to `self.bin_size`
            x (int, optional): X position of guide star on ccd
            y (int, optional): Y position of guide star on ccd

        Returns:
            bool: Indicates if guide position was successfully sent
        """
        response = {}
        if self.is_connected:

            assert x is not None, self.logger.warning("X position required")
            assert y is not None, self.logger.warning("Y position required")

            if bin_size is None:
                bin_size = self.bin_size

            response = self.query('guider/set_guide_position.js', {
                'bin': bin_size,
                'x': x,
                'y': y
            })

        return response.get('success', False)

    def regulate_temperature(self):
        """ Regulate guider temperature

        Returns:
            bool: Indicates if temperature regulation has turned on
        """
        response = {}
        if self.is_connected:
            response = self.query('guider/regulate_temperature.js')

        return response.get('success', False)

    def take_exposure(self, bin_size=None, exp_time=1, filename=None):
        """ Take an image with the guider

        Args:
            bin_size (None, optional): Description
            exp_time (float, optional): Number of seconds to expose
            filename (str, optional): Pathname for guide image

        Returns:
            bool: Indicates if image was successfully taken
        """
        response = {}
        if self.is_connected:

            if bin_size is None:
                bin_size = self.bin_size

            if filename is None:
                filename = self.image_path

            self.logger.debug("Taking {} sec guide exposure with {} binning".format(exp_time, bin_size))

            response = self.query('guider/take_image.js', {
                'bin': bin_size,
                'exptime': exp_time,
                'path': filename,
            })

        return response.get('success', False)

    def find_guide_star(self):
        """ Find a guide star

        Uses DAOStar find the `photutils` package to find all point sources in
        the image after sigma clipping. The 10th best match is selected and the
        X and Y pixel coordinates are returned.

        Returns:
            tuple(int, int): X and Y pixel coordinates of matched star
        """
        self.logger.debug("Finding point sources in image")
        data = fits.getdata(self.image_path)
        mean, median, std = sigma_clipped_stats(data)
        daofind = DAOStarFinder(fwhm=3.0, threshold=5. * std)
        sources = daofind(data - median)
        sources.sort('flux')
        sources.reverse()

        selected = sources[9]  # 10th best match
        x = selected['xcentroid']
        y = selected['ycentroid']

        self.logger.debug("Found star at pixel coordinates ({}, {})".format(x, y))
        return x, y

    def autoguide(self, timeout=30):
        """ Perform autoguiding

        Args:
            timeout (int, optional): Timeout in seconds to wait for the guide image,
            defaults to 30 seconds

        Returns:
            bool: Indicates if guiding was successfully started

        Raises:
            error.PanError: Error raised if guide image does not appear
        """
        success = False
        if self.is_connected:
            self.logger.debug("Starting autoguider")

            # Remove existing image
            try:
                os.remove(self.image_path)
            except FileNotFoundError:
                pass

            self.logger.debug("Getting autoguiding image")
            self.take_exposure()

            count = 0
            while not os.path.exists(self.image_path):
                self.logger.debug("Waiting for guide image")
                time.sleep(1)
                count += 1

                if count == timeout:
                    raise error.PanError("Problem getting autoguide image")

            try:
                x, y = self.find_guide_star()
            except Exception as e:
                raise error.PanError("Can't find guide star in image, guiding not turned on")

            self.logger.debug("Setting guide star at CCD coordinates: {} {}".format(x, y))
            self.set_guide_position(x=x, y=y)

            self.logger.debug("Starting autoguide")
            success = self.start_guiding()

        return success


##################################################################################################
# Communication Methods
##################################################################################################

    def query(self, template, params=None):
        """ Query the guider

        Args:
            template (str): Name of template file stored in `templates_dir`
            params (dict, optional): Parameters required by the template

        Returns:
            dict: Response from guider, including `success` (bool) and `msg` (str)
                as well as command-specific items
        """
        self.write(self._get_command(template, params=params))
        response = self.read()
        return response

    def write(self, value):
        """ Write to the guider

        Note:
            This method is usually just called via `query`

        Args:
            value (str): String to be written to guider, usually given by template
        """
        self.theskyx.write(value)

    def read(self, timeout=5):
        """ Read response from guider

        Args:
            timeout (int, optional): Timeout in seconds for attempting to get a response

        Returns:
            dict: Object representing the response, see `query`
        """
        while True:
            response = self.theskyx.read()
            if response is not None or timeout == 0:
                break
            else:
                time.sleep(1)
                timeout -= 1

        try:
            response_obj = json.loads(response)
        except TypeError as e:
            self.logger.warning("Error: {}".format(e, response))
        except json.JSONDecodeError as e:
            response_obj = {
                "response": response,
                "success": False,
            }

        return response_obj

##################################################################################################
# Private Methods
##################################################################################################

    def _get_command(self, filename, params=None):
        """ Looks up appropriate command for telescope """

        if filename.startswith('/') is False:
            filename = os.path.join(self.template_dir, filename)

        template = ''
        try:
            with open(filename, 'r') as f:
                template = Template(f.read())
        except Exception as e:
            self.logger.warning("Problem reading TheSkyX template {}: {}".format(filename, e))

        if params is None:
            params = {}

        params.setdefault('async', 'false')

        return template.safe_substitute(params)
