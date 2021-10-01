from astropy import units as u
from panoptes.pocs.camera.gphoto.base import AbstractGPhotoCamera
from panoptes.utils import error
from panoptes.utils.time import current_time
from panoptes.utils.utils import get_quantity_value


class Camera(AbstractGPhotoCamera):

    def __init__(self, readout_time: float = 1.0, file_extension: str = 'cr2', connect: bool = True,
                 *args, **kwargs):
        """Create a camera object for a Canon EOS DSLR.

        Args:
            readout (float): The time it takes to read out the file from the
                camera, default 1.0 second.
            file_extension (str): The file extension to use, default `cr2`.
            connect (bool): Connect to camera on startup, default True.
        """
        kwargs['readout_time'] = readout_time
        kwargs['file_extension'] = file_extension
        super().__init__(*args, **kwargs)
        self.logger.debug("Creating Canon DSLR GPhoto2 camera")

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
            '/main/capturesettings/autoexposuremode': 3,  # 3 - Manual; 4 - Bulb
            '/main/capturesettings/continuousaf': 0,  # No auto-focus
            '/main/capturesettings/drivemode': 0,  # Single exposure
            '/main/capturesettings/focusmode': 0,  # Manual (don't try to focus)
            '/main/imgsettings/imageformat': 9,  # RAW
            '/main/imgsettings/imageformatcf': 9,  # RAW
            '/main/imgsettings/imageformatsd': 9,  # RAW
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
            '/main/actions/syncdatetime': "1",
        }

        self.set_properties(prop2index=prop2index, prop2value=prop2value)

        # TODO check this works on all Canon models.
        self.model = self.get_property('d402')

        self._connected = True

    def _start_exposure(self,
                        seconds=None,
                        filename=None,
                        dark=False,
                        header=None,
                        iso=100,
                        *args, **kwargs):
        """Start the exposure.

        Tested With:
            * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure.
            filename (str, optional): Image is saved to this filename.
            header (dict, optional): The metadata to be added as FITS headers.
            iso (int, optional): The ISO setting to use for the exposure, default 100.
        """
        # Make sure we have just the value, no units
        seconds = get_quantity_value(seconds)

        cmd_args = [
            f'--set-config-index', 'shutterspeed=0',
            f'--set-config', f'iso={iso}',
            f'--set-config-index', 'eosremoterelease=2',
            f'--wait-event={int(seconds):d}s',
            f'--set-config-index', 'eosremoterelease=4',
            f'--wait-event-and-download=1s',
            f'--filename', f'{filename}'
        ]

        try:
            self.command(cmd_args)
        except error.InvalidCommand as e:
            self.logger.warning(e)
        else:
            readout_args = (filename, header)
            return readout_args
