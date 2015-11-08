import re
import os
import datetime

from astropy.time import Time

from .camera import AbstractGPhotoCamera

from ..utils.logger import has_logger


@has_logger
class Camera(AbstractGPhotoCamera):

    def __init__(self, config=dict(), *args, **kwargs):

        super().__init__(config)

        self.last_start_time = None

    def connect(self):
        """
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        """
        self.logger.info('Connecting to camera')
        # self.load_properties()

        self.set_property('/main/settings/autopoweroff', 0)     # Don't power off
        self.set_property('/main/actions/viewfinder', 0)       # Screen off
        self.set_property('/main/settings/reviewtime', 0)       # Screen off
        self.set_property('/main/settings/capturetarget', 0)    # SD Card
        self.set_property('/main/settings/artist', 'Project PANOPTES')
        self.set_property('/main/settings/ownername', 'Project PANOPTES')
        self.set_property('/main/settings/copyright', 'Project PANOPTES 2015')
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

        # Get Camera Properties
        # self.get_serial_number()

        self._connected = True

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera

        Returns:
            str:    Filename format
        """

        today_dir = '/var/panoptes/images/{}'.format(Time.now().isot.split('T')[0].replace('-', ''))

        if self.last_start_time:
            filename = self.last_start_time.strftime('{}/{}_%Y%m%dT%H%M%S.cr2'.format(today_dir, self.name))
        else:
            filename = self.last_start_time.strftime('{}/{}.cr2'.format(today_dir, self.name))

        return filename

    @property
    def is_connected(self):
        """ Is the camera available vai gphoto2 """
        return self._connected

    def take_exposure(self, seconds=0.05):
        """ Take an exposure for given number of seconds


        Note:
            gphoto2 --wait-event=2s --set-config eosremoterelease=2 --wait-event=10s --set-config eosremoterelease=4 --wait-event-and-download=5s

            Tested With:
                * Canon EOS 100D

        Args:
            seconds(float):     Exposure time, defaults to 0.05 seconds
        """

        self.logger.debug('Taking {} second exposure'.format(seconds))

        self.last_start_time = datetime.datetime.now()

        filename = self.construct_filename()

        cmd = [
            '--set-config', 'eosremoterelease=Immediate',
            '--wait-event={:d}s'.format(int(seconds)),
            '--set-config', 'eosremoterelease=4',
            '--wait-event-and-download=1s',
            '--filename={:s}'.format(filename),
        ]

        result = self.command(cmd)

        # Check for result
        saved_file_name = None
        for line in result:
            IsSavedFile = re.match('Saving file as (.+\.[cC][rR]2)', line)
            if IsSavedFile:
                if os.path.exists(IsSavedFile.group(1)):
                    saved_file_name = IsSavedFile.group(1)

        end_time = datetime.datetime.now()
        elapsed = (end_time - self.last_start_time).total_seconds()

        self.logger.debug('  Elapsed time = {:.1f} s'.format(elapsed))
        self.logger.debug('  Overhead time = {:.1f} s'.format(elapsed - seconds))

        return saved_file_name
