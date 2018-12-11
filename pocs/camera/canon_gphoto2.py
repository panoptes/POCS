import os
import subprocess

from astropy import units as u
from threading import Event
from threading import Timer

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils.images import cr2 as cr2_utils
from pocs.camera import AbstractGPhotoCamera


class Camera(AbstractGPhotoCamera):

    def __init__(self, *args, **kwargs):
        kwargs['readout_time'] = 6.0
        kwargs['file_extension'] = 'cr2'
        super().__init__(*args, **kwargs)
        self.logger.debug("Connecting GPhoto2 camera")
        self.connect()
        self.logger.debug("{} connected".format(self.name))

    def connect(self):
        """Connect to Canon DSLR

        Gets the serial number from the camera and sets various settings
        """
        self.logger.debug('Connecting to camera')

        # Get serial number
        _serial_number = self.get_property('serialnumber')
        if not _serial_number:
            raise error.CameraNotFound("Camera not responding: {}".format(self))

        self._serial_number = _serial_number

        # Properties to be set upon init.
        prop2index = {
            '/main/actions/viewfinder': 1,                # Screen off
            '/main/capturesettings/autoexposuremode': 3,  # 3 - Manual; 4 - Bulb
            '/main/capturesettings/continuousaf': 0,      # No auto-focus
            '/main/capturesettings/drivemode': 0,         # Single exposure
            '/main/capturesettings/focusmode': 0,         # Manual (don't try to focus)
            '/main/capturesettings/shutterspeed': 0,      # Bulb
            '/main/imgsettings/imageformat': 9,           # RAW
            '/main/imgsettings/imageformatcf': 9,         # RAW
            '/main/imgsettings/imageformatsd': 9,         # RAW
            '/main/imgsettings/iso': 1,                   # ISO 100
            '/main/settings/autopoweroff': 0,             # Don't power off
            '/main/settings/capturetarget': 0,            # Capture to RAM, for download
            '/main/settings/datetime': 'now',             # Current datetime
            '/main/settings/datetimeutc': 'now',          # Current datetime
            '/main/settings/reviewtime': 0,               # Screen off after taking pictures
        }

        owner_name = 'Project PANOPTES'
        artist_name = self.config.get('unit_id', owner_name)
        copyright = 'owner_name {}'.format(owner_name, current_time().datetime.year)

        prop2value = {
            '/main/settings/artist': artist_name,
            '/main/settings/copyright': copyright,
            '/main/settings/ownername': owner_name,
        }

        self.set_properties(prop2index, prop2value)
        self._connected = True

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls
        `take_exposure`. Also creates a `threading.Event` object and a
        `threading.Timer` object. The timer calls `process_exposure` after the
        set amount of time is expired (`observation.exp_time + self.readout_time`).

        Note:
            If a `filename` is passed in it can either be a full path that includes
            the extension, or the basename of the file, in which case the directory
            path and extension will be added to the `filename` for output

        Args:
            observation (~pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict): Header data to be saved along with the file
            filename (str, optional): Filename for saving, defaults to ISOT time stamp
            **kwargs (dict): Optional keyword arguments (`exp_time`)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        camera_event = Event()

        exp_time, file_path, image_id, metadata = self._setup_observation(observation,
                                                                          headers,
                                                                          filename,
                                                                          *args,
                                                                          **kwargs)

        proc = self.take_exposure(seconds=exp_time, filename=file_path)

        # Add most recent exposure to list
        if self.is_primary:
            if 'POINTING' in headers:
                observation.pointing_images[image_id] = file_path.replace('.cr2', '.fits')
            else:
                observation.exposure_list[image_id] = file_path.replace('.cr2', '.fits')

        # Process the image after a set amount of time
        wait_time = exp_time + self.readout_time
        t = Timer(wait_time, self.process_exposure, (metadata, camera_event, proc))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None, *args, **kwargs):
        """Take an exposure for given number of seconds and saves to provided filename

        Note:
            See `scripts/take_pic.sh`

            Tested With:
                * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
        """
        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug(
            'Taking {} second exposure on {}: {}'.format(
                seconds, self.name, filename))

        if isinstance(seconds, u.Quantity):
            seconds = seconds.value

        script_path = '{}/scripts/take_pic.sh'.format(os.getenv('POCS'))

        run_cmd = [script_path, self.port, str(seconds), filename]

        # Take Picture
        try:
            proc = subprocess.Popen(run_cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        except error.InvalidCommand as e:
            self.logger.warning(e)
        except subprocess.TimeoutExpired:
            self.logger.debug("Still waiting for camera")
            proc.kill()
            outs, errs = proc.communicate(timeout=10)
            if errs is not None:
                self.logger.warning(errs)
        else:
            return proc

    def _process_fits(self, file_path, info):
        """
        Converts the CR2 to a FITS file
        """
        self.logger.debug("Converting CR2 -> FITS: {}".format(file_path))
        fits_path = cr2_utils.cr2_to_fits(file_path, headers=info, remove_cr2=False)
        # Replace the path name with the FITS file
        info['file_path'] = fits_path
        return fits_path
