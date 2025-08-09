import time

import gphoto2 as gp
from astropy import units as u
from panoptes.utils import error
from panoptes.utils.time import current_time
from panoptes.utils.utils import get_quantity_value

from panoptes.pocs.camera.gphoto.base import AbstractGPhotoCamera


class Camera(AbstractGPhotoCamera):

    def __init__(
            self, readout_time: float = 1.0, file_extension: str = 'cr2', setup_properties: bool = False,
            *args, **kwargs
    ):
        """Create a camera object for a Canon EOS DSLR.
        Args:
            readout (float): The time it takes to read out the file from the
                camera, default 1.0 second.
            file_extension (str): The file extension to use, default `cr2`.
            setup_properties (bool): If True, will call `setup_camera()` to set
                properties on the camera.
        """
        kwargs['readout_time'] = readout_time
        kwargs['file_extension'] = file_extension
        super().__init__(*args, **kwargs)
        self.logger.debug("Creating Canon DSLR GPhoto2 camera")

        self.connect()

        if setup_properties:
            self.setup_camera()

    @property
    def bit_depth(self):
        return 12 * u.bit

    @property
    def egain(self):
        return 1.5 * (u.electron / u.adu)

    def connect(self):
        """Connect to the camera.
        This will attempt to connect to the camera using gphoto2.
        """
        super().connect()
        # Get serial number
        _serial_number = self.get_property('serialnumber')
        if not _serial_number:
            raise error.CameraNotFound(f"Camera not responding: {self}")

        self._serial_number = _serial_number

    def setup_camera(self):
        """Set up the camera.
        Usually called as part of an initial setup, this will set properties
        on the canon cameras that should persist across power cycles.
        """
        # Properties to be set upon init.
        owner_name = 'PANOPTES'
        artist_name = self.get_config('pan_id', default=owner_name)
        copy_right = f'{owner_name}_{current_time().datetime:%Y}'

        prop2value = {
            'drivemode': 'Single',
            'focusmode': 'Manual',
            'imageformat': 'RAW',
            # 'autoexposuremode': 'Manual',  # Need physical toggle.
            # 'imageformatsd': 'RAW',  # We shouldn't need to set this.
            'capturetarget': 'Internal RAM',
            'reviewtime': 'None',
            'iso': '100',
            'shutterspeed': 'bulb',
            'artist': artist_name,
            'copyright': copy_right,
            'ownername': owner_name,
        }

        self.set_properties(prop2value=prop2value)

        self.model = self.get_property('model')

    def _start_exposure(
            self,
            seconds=None,
            filename=None,
            dark=False,
            header=None,
            iso=100,
            *args, **kwargs
    ):
        """Start the exposure.
        Tested With:
            * Canon EOS 100D
        Args:
            seconds (u.second, optional): Length of exposure.
            filename (str, optional): Image is saved to this filename.
            header (dict or Header, optional): The metadata to be added as FITS headers.
            iso (int, optional): The ISO setting to use for the exposure, default 100.
        """
        # Make sure we have just the value, no units
        seconds = get_quantity_value(seconds)

        try:
            self.set_property('iso', str(iso))

            # Set shutter speed
            shutter_speed = self.get_shutter_speed(seconds)

            if shutter_speed == 'bulb':
                # Bulb setting.
                self.set_property('eosremoterelease', 'Press')
                time.sleep(seconds)
                self.set_property('eosremoterelease', 'Release')
            else:
                self.set_property('shutterspeed', shutter_speed)
                self.gphoto2.capture(gp.GP_CAPTURE_IMAGE)

        except error.InvalidCommand as e:
            self.logger.warning(e)
        else:
            readout_args = (filename, header)
            return readout_args

    def get_shutter_speed(self, seconds: float):
        """Looks up the appropriate shutterspeed setting for the given seconds.
        If the given seconds does not match a set shutterspeed, the 'bulb' setting
        is returned.
        """
        seconds = get_quantity_value(seconds, unit='second')
        # TODO derive these from `load_properties`.
        shutter_speeds = self.load_properties().get('shutterspeed', {}).get('choices', [])

        if seconds in shutter_speeds:
            return seconds
        else:
            # Find the closest shutter speed
            if len(shutter_speeds) > 0:
                return min(shutter_speeds, key=lambda x: abs(float(x) - seconds))
            else:
                return 'bulb'
