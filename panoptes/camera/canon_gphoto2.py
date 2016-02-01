import os

from astropy import units as u

from .camera import AbstractGPhotoCamera
from ..utils import error
from ..utils import current_time


class Camera(AbstractGPhotoCamera):

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.logger.debug("Initializing GPhoto2 camera")

    def connect(self):
        """
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        """
        self.logger.debug('Connecting to camera')

        self.set_property('/main/actions/viewfinder', 0)       # Screen off
        self.set_property('/main/settings/autopoweroff', 0)     # Don't power off
        self.set_property('/main/settings/reviewtime', 0)       # Screen off
        self.set_property('/main/settings/capturetarget', 0)    # SD Card
        self.set_property('/main/settings/artist', '\"Project PANOPTES\"')
        self.set_property('/main/settings/ownername', '\"Project PANOPTES\"')
        self.set_property('/main/settings/copyright', '\"Project PANOPTES 2016\"')
        self.set_property('/main/imgsettings/imageformat', 9)       # RAW
        self.set_property('/main/imgsettings/imageformatsd', 9)     # RAW
        self.set_property('/main/imgsettings/imageformatcf', 9)     # RAW
        self.set_property('/main/imgsettings/iso', 1)               # ISO 100
        self.set_property('/main/capturesettings/focusmode', 0)         # Manual
        self.set_property('/main/capturesettings/continuousaf', 0)         # No AF
        self.set_property('/main/capturesettings/autoexposuremode', 3)  # 3 - Manual; 4 - Bulb
        self.set_property('/main/capturesettings/drivemode', 0)         # Single exposure
        self.set_property('/main/capturesettings/shutterspeed', 0)      # Bulb
        self.set_property('/main/actions/syncdatetime', 1)  # Sync date and time to computer
        self.set_property('/main/actions/uilock', 1)        # Don't let the UI change

        # Get serial number
        self._serial_number = self.get_property('serialnumber')

        self._connected = True

    @property
    def uid(self):
        return self._serial_number[0:6]

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera

        Returns:
            str:    Filename format
        """

        now = current_time().datetime.strftime("%Y/%m/%dT%H%M%S")
        date, time = now.split('T')

        filename = os.path.join(
            self._image_dir, self._serial_number, date, "{}.cr2".format(time))

        return filename

    @property
    def is_connected(self):
        """ Is the camera available vai gphoto2 """
        return self._connected

    def take_exposure(self, seconds=1.0 * u.second, filename=None, **kwargs):
        """ Take an exposure for given number of seconds


        Note:
            `gphoto2 --wait-event=2s
                --set-config eosremoterelease=2
                --wait-event=10s
                --set-config eosremoterelease=4
                --wait-event-and-download=5s`

            Tested With:
                * Canon EOS 100D

        Args:
            seconds(float):     Exposure time, defaults to 0.05 seconds
        """

        self.logger.debug('Taking {} second exposure on {}'.format(seconds, self.name))

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        if filename is None:
            filename = self.construct_filename()

        cmd = [
            '--set-config', 'eosremoterelease=Immediate',
            '--wait-event={:d}s'.format(int(seconds.value)),
            '--set-config', 'eosremoterelease=4',
            '--wait-event-and-download=1s',
            '--filename={:s}'.format(filename),
        ]

        # Send command to camera
        try:
            self.command(cmd)
        except error.InvalidCommand as e:
            self.logger.warning(e)

        return filename
