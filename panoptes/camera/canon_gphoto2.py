import re
import os

from astropy.time import Time

from .camera import AbstractGPhotoCamera

from ..utils import error


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

        now = '{}'.format(Time.now().isot.replace('-', '').replace(':', '').split('.')[0])  # Ugh
        filename = os.path.join(self._image_dir, self._serial_number, now + '.cr2')

        return filename

    @property
    def is_connected(self):
        """ Is the camera available vai gphoto2 """
        return self._connected

    def take_exposure(self, seconds=1.0):
        """ Take an exposure for given number of seconds


        Note:
            `gphoto2 --wait-event=2s --set-config eosremoterelease=2 --wait-event=10s --set-config eosremoterelease=4 --wait-event-and-download=5s`

            Tested With:
                * Canon EOS 100D

        Note:
            If `callback` is set to None (default), then `take_exposure` will
            call `process_image` by default.

        Args:
            seconds(float):     Exposure time, defaults to 0.05 seconds
            callback:           Callback method, defaults to `process_image`.
        """

        self.logger.debug('Taking {} second exposure on {}'.format(seconds, self.name))

        filename = self.construct_filename()

        cmd = [
            '--set-config', 'eosremoterelease=Immediate',
            '--wait-event={:d}s'.format(int(seconds)),
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

    def process_image(self):
        """ Command to be run after an image is taken.

        Called from `take_exposure` and set by a timer. Checks for output
        from the running command for file name.

        Args:
            filename(str):  Image to be processed
        """
        self.logger.debug("Processing image")

        result = self.get_command_result()

        # self.logger.debug(result)

        # Check for result
        saved_file_name = None
        for line in result.split('\n'):
            match_filename = re.match('Saving file as (.*\.[cC][rR]2)', line)
            if match_filename:
                saved_file_name = match_filename.group(1)
                if os.path.exists(saved_file_name):
                    self.logger.debug("Image saved: {}".format(saved_file_name))

        return saved_file_name
