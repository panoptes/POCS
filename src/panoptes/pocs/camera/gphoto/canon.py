from astropy import units as u
from panoptes.pocs.camera.gphoto import AbstractGPhotoCamera
from panoptes.utils import error
from panoptes.utils.time import current_time


class Camera(AbstractGPhotoCamera):

    def __init__(self, readout=1.0, file_extension='cr2', connect=True, *args, **kwargs):
        """Create a camera object for a Canon EOS DSLR."""
        self.logger.debug("Creating Canon DSLR GPhoto2 camera")
        super().__init__(readout_time=readout, file_extension=file_extension, *args, **kwargs)

        if connect:
            self.connect()

    @property
    def bit_depth(self):
        return 12 * u.bit

    @property
    def egain(self):
        return 1.5 * (u.electron / u.adu)

    def connect(self):
        """Connect to Canon DSLR.

        Gets the serial number from the camera and sets various settings.
        """
        self.logger.debug('Connecting to Canon gphoto2 camera')

        # Get serial number
        _serial_number = self.get_property('serialnumber')
        if not _serial_number:
            raise error.CameraNotFound(f"Camera not responding: {self}")

        self._serial_number = _serial_number

        # Properties to be set upon init.
        prop2index = {
            '/main/actions/viewfinder': 1,  # Screen off
            '/main/capturesettings/autoexposuremode': 3,  # 3 - Manual; 4 - Bulb
            '/main/capturesettings/continuousaf': 0,  # No auto-focus
            '/main/capturesettings/drivemode': 0,  # Single exposure
            '/main/capturesettings/focusmode': 0,  # Manual (don't try to focus)
            '/main/imgsettings/imageformat': 9,  # RAW
            '/main/imgsettings/imageformatcf': 9,  # RAW
            '/main/imgsettings/imageformatsd': 9,  # RAW
            '/main/settings/autopoweroff': 0,  # Don't power off
            '/main/settings/capturetarget': 0,  # Capture to RAM, for download
            '/main/settings/reviewtime': 0,  # Screen off after taking pictures
            '/main/imgsettings/iso': 1,  # ISO 100
            '/main/capturesettings/shutterspeed': 0,  # Bulb
        }

        owner_name = 'Project PANOPTES'
        artist_name = self.get_config('pan_id', default=owner_name)
        copy_right = f'{owner_name} {current_time().datetime:%Y}'

        prop2value = {
            '/main/settings/artist': artist_name,
            '/main/settings/copyright': copy_right,
            '/main/settings/ownername': owner_name,
            # Current UTC datetime in seconds since epoch.U
            '/main/settings/datetimeutc': f'{current_time(datetime=True):%s}',
        }

        self.set_properties(prop2index=prop2index, prop2value=prop2value)
        self._connected = True
